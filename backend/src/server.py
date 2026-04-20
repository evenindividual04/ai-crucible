"""
FastAPI WebSocket server for AI Crucible War Room Dashboard.

Provides real-time streaming of Crucible simulation events to frontend.
"""

import sys
import json
import uuid
import os
import secrets
import time
import hashlib
import hmac
from pathlib import Path
from contextlib import asynccontextmanager

# Add the main package source to path so the backend venv can import crucible
_repo_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_repo_root / "src"))

# Load .env from repo root so API keys are available
from dotenv import load_dotenv
load_dotenv(_repo_root / ".env")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
import asyncio
import logging

# Import mock server for development
from .mock_server import send_mock_simulation
from .database import (
    create_db_and_tables,
    get_run,
    get_session,
    list_run_events,
    RunRecord,
    RunEventRecord,
)
from .demo_runs import DEMO_RUNS, list_demo_runs
from .queue import redis_client
from .tasks import run_simulation_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_CREATE_RUN_WINDOW_SECONDS = 60
_CREATE_RUN_MAX_REQUESTS = 20
_create_run_timestamps: dict[str, list[float]] = {}
_WS_HANDSHAKE_TIMEOUT_SECONDS = 5
_WS_WINDOW_SECONDS = 60
_WS_MAX_CONNECTS = 40
_WS_MAX_ACTIONS = 120
_ws_timestamps: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title="AI Crucible API",
    description="Real-time WebSocket API for War Room Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app"  # For production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimulationRequest(BaseModel):
    """Request to start a simulation"""
    prompt: str
    config: Optional[Dict[str, Any]] = None
    use_mock: bool = True  # Use mock data by default for development


class CreateRunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    config: Optional[Dict[str, Any]] = None
    mode: Literal["live", "demo"] = "live"
    demo_id: Optional[str] = None


class RunSummaryResponse(BaseModel):
    run_id: str
    status: str
    mode: str
    task_id: Optional[str] = None
    access_token: Optional[str] = None


def _enforce_live_run_access(http_request: Request) -> None:
    live_enabled = os.getenv("CRUCIBLE_ENABLE_LIVE_RUNS", "true").lower() == "true"
    if not live_enabled:
        raise HTTPException(status_code=403, detail="Live runs are disabled")

    expected_api_key = os.getenv("CRUCIBLE_API_KEY")
    if not expected_api_key:
        raise HTTPException(status_code=503, detail="Live runs are not configured")

    provided_api_key = http_request.headers.get("x-api-key", "")
    if provided_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _enforce_websocket_access(websocket: WebSocket) -> None:
    expected_api_key = os.getenv("CRUCIBLE_API_KEY")
    if expected_api_key:
        provided_api_key = websocket.headers.get("x-api-key", "")
        if provided_api_key != expected_api_key:
            raise HTTPException(status_code=401, detail="Unauthorized")


def _enforce_live_run_websocket_access(websocket: WebSocket) -> None:
    live_enabled = os.getenv("CRUCIBLE_ENABLE_LIVE_RUNS", "true").lower() == "true"
    if not live_enabled:
        raise HTTPException(status_code=403, detail="Live runs are disabled")
    _enforce_websocket_access(websocket)


def _enforce_live_run_read_access(http_request: Request, run: RunRecord) -> None:
    if run.mode != "live":
        return

    expected_api_key = os.getenv("CRUCIBLE_API_KEY")
    if not expected_api_key:
        raise HTTPException(status_code=503, detail="Live runs are not configured")

    provided_api_key = http_request.headers.get("x-api-key", "")
    if provided_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _enforce_run_owner_access(run: RunRecord, provided_token: str) -> None:
    if not provided_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    provided_hash = hashlib.sha256(provided_token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(provided_hash, run.access_token_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _client_identity(http_request: Request) -> str:
    trust_proxy = os.getenv("CRUCIBLE_TRUST_PROXY_HEADERS", "false").lower() == "true"
    if trust_proxy:
        forwarded = http_request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return http_request.client.host if http_request.client else "unknown"


def _websocket_client_identity(websocket: WebSocket) -> str:
    trust_proxy = os.getenv("CRUCIBLE_TRUST_PROXY_HEADERS", "false").lower() == "true"
    if trust_proxy:
        forwarded = websocket.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return websocket.client.host if websocket.client else "unknown"


def _enforce_ws_rate_limit(client_key: str, action: str, max_requests: int) -> None:
    key = f"rl:ws:{action}:{client_key}:{int(time.time() // _WS_WINDOW_SECONDS)}"
    try:
        client = redis_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, _WS_WINDOW_SECONDS)
        if count > max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except HTTPException:
        raise
    except Exception:
        logger.warning("Redis websocket rate limiter unavailable, using process-local fallback")

    fallback_key = f"ws:{action}:{client_key}"
    now = time.time()
    window_start = now - _WS_WINDOW_SECONDS
    recent = [ts for ts in _ws_timestamps.get(fallback_key, []) if ts >= window_start]
    if len(recent) >= max_requests:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    recent.append(now)
    _ws_timestamps[fallback_key] = recent


def _enforce_create_run_rate_limit(http_request: Request) -> None:
    client_ip = _client_identity(http_request)

    # Primary limiter: Redis fixed-window counter to work across instances.
    try:
        window = int(time.time() // _CREATE_RUN_WINDOW_SECONDS)
        key = f"rl:create_run:{client_ip}:{window}"
        client = redis_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, _CREATE_RUN_WINDOW_SECONDS)
        if count > _CREATE_RUN_MAX_REQUESTS:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return
    except HTTPException:
        raise
    except Exception:
        logger.warning("Redis rate limiter unavailable, using process-local fallback")

    # Fallback for local/dev runs when Redis is unavailable.
    now = time.time()
    window_start = now - _CREATE_RUN_WINDOW_SECONDS

    recent = [ts for ts in _create_run_timestamps.get(client_ip, []) if ts >= window_start]
    if len(recent) >= _CREATE_RUN_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    recent.append(now)
    _create_run_timestamps[client_ip] = recent


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "AI Crucible WebSocket Server",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "websocket": "ready",
        "timestamp": asyncio.get_event_loop().time()
    }


@app.get("/demo-runs")
async def demo_runs() -> dict[str, Any]:
    return {"items": list_demo_runs()}


@app.post("/runs", response_model=RunSummaryResponse)
async def create_run(request: CreateRunRequest, http_request: Request) -> RunSummaryResponse:
    _enforce_create_run_rate_limit(http_request)

    demo = None
    if request.mode == "demo":
        demo_id = request.demo_id or "payments-gateway"
        demo = DEMO_RUNS.get(demo_id)
        if not demo:
            raise HTTPException(status_code=404, detail=f"Unknown demo_id: {demo_id}")
    else:
        _enforce_live_run_access(http_request)

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    access_token = secrets.token_urlsafe(24)
    access_token_hash = hashlib.sha256(access_token.encode("utf-8")).hexdigest()

    with get_session() as session:
        run = RunRecord(
            id=run_id,
            prompt=request.prompt,
            access_token_hash=access_token_hash,
            mode=request.mode,
            status="queued",
        )
        session.add(run)
        session.commit()

    if request.mode == "demo" and demo is not None:
        with get_session() as session:
            run = session.get(RunRecord, run_id)
            if run:
                run.status = "completed"
                run.summary_json = demo["events"][-1]["data"]
                run.score = float(demo["events"][-1]["data"].get("security_score", 0))
                session.add(run)

            for event in demo["events"]:
                session.add(
                    RunEventRecord(
                        run_id=run_id,
                        event_type=event["type"],
                        payload_json=event["data"],
                    )
                )
            session.commit()

        return RunSummaryResponse(run_id=run_id, status="completed", mode="demo", access_token=access_token)

    try:
        task = run_simulation_task.delay(run_id=run_id, prompt=request.prompt, config=request.config or {})
    except Exception as exc:
        logger.exception("Failed to enqueue run %s", run_id)
        with get_session() as session:
            run = session.get(RunRecord, run_id)
            if run:
                run.status = "failed"
                run.error = "enqueue_failed"
                session.add(run)
                session.commit()
        raise HTTPException(status_code=503, detail="Simulation queue unavailable") from exc

    return RunSummaryResponse(
        run_id=run_id,
        status="queued",
        mode="live",
        task_id=task.id,
        access_token=access_token,
    )


@app.get("/runs/{run_id}")
async def get_run_status(run_id: str, http_request: Request) -> dict[str, Any]:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    _enforce_live_run_read_access(http_request, run)
    _enforce_run_owner_access(run, http_request.headers.get("x-run-token", ""))

    return {
        "run_id": run.id,
        "status": run.status,
        "mode": run.mode,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "score": run.score,
        "grade": run.grade,
        "summary": run.summary_json,
        "error": run.error,
    }


@app.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    http_request: Request,
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run_not_found")
    _enforce_live_run_read_access(http_request, run)
    _enforce_run_owner_access(run, http_request.headers.get("x-run-token", ""))

    events = list_run_events(run_id, limit=limit)
    return {
        "run_id": run_id,
        "events": [
            {
                "id": event.id,
                "type": event.event_type,
                "data": event.payload_json,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


async def _stream_run_subscription(websocket: WebSocket, run_id: str) -> None:
    # Replay persisted events so reconnecting or late subscribers get full context.
    replay_events = list_run_events(run_id, limit=1000)
    run = get_run(run_id)

    if not replay_events and run is None:
        await websocket.send_json({"type": "ERROR", "data": {"message": "run_not_found"}})
        return

    for event in replay_events:
        await websocket.send_json({"type": event.event_type, "data": event.payload_json})

    if replay_events and replay_events[-1].event_type in ("SIMULATION_END", "ERROR"):
        return

    if run and run.status in ("completed", "failed"):
        await websocket.send_json({"type": "RUN_STATUS", "data": {"status": run.status}})
        return

    channel = f"run:{run_id}:events"
    try:
        client = redis_client()
        pubsub = client.pubsub()
        pubsub.subscribe(channel)
    except Exception:
        logger.exception("Redis subscription unavailable for run %s", run_id)
        return

    idle_ticks = 0
    try:
        while True:
            message = await asyncio.to_thread(
                pubsub.get_message,
                ignore_subscribe_messages=True,
                timeout=1.0,
            )

            if message and message.get("data"):
                payload = json.loads(message["data"])
                await websocket.send_json(payload)
                idle_ticks = 0
                if payload.get("type") in ("SIMULATION_END", "ERROR"):
                    return
                continue

            idle_ticks += 1
            run = get_run(run_id)
            if run and run.status in ("completed", "failed") and idle_ticks >= 2:
                await websocket.send_json({"type": "RUN_STATUS", "data": {"status": run.status}})
                return
            if idle_ticks >= 300:
                return
    finally:
        pubsub.unsubscribe(channel)
        pubsub.close()


async def run_real_simulation(websocket: WebSocket, prompt: str, config: Dict[str, Any]) -> None:
    """
    Run the real Crucible engine and stream events over the WebSocket.

    The graph's red_team_node calls asyncio.run() internally, so the entire
    synchronous run_crucible() must execute in a thread to avoid clashing
    with FastAPI's running event loop.
    """
    from crucible.graph import run_crucible
    from crucible.patches_v2 import IncrementalPatch

    logger.info(f"Starting real simulation for prompt: {prompt[:60]}...")

    # Run the blocking simulation in a thread pool
    final_state = await asyncio.to_thread(run_crucible, prompt)

    if final_state is None:
        await websocket.send_json({
            "type": "ERROR",
            "data": {"message": "Simulation returned no state"},
        })
        return

    # Emit components
    for comp in final_state.design_components:
        await websocket.send_json({
            "type": "COMPONENT_CREATED",
            "data": {
                "id": comp.component_id,
                "name": comp.name,
                "type": "service",
                "dependencies": comp.dependencies,
            },
        })
        await asyncio.sleep(0.1)

    # Emit iteration summary events
    current_iter = 0
    for summary in final_state.iteration_summaries:
        current_iter += 1
        await websocket.send_json({
            "type": "ITERATION_START",
            "data": {
                "iteration": current_iter,
                "max_iterations": final_state.max_iterations,
            },
        })

        # Emit agent spawns for this iteration
        for agent_name in final_state.active_agents:
            await websocket.send_json({
                "type": "AGENT_SPAWN",
                "data": {"id": f"{agent_name}_i{current_iter}", "name": agent_name, "type": "RED_TEAM"},
            })

        # Emit vulnerabilities found in this iteration
        iter_vuln_ids = set(summary.vulnerabilities_reported)
        for vuln in final_state.vulnerabilities:
            if vuln.vulnerability_id in iter_vuln_ids:
                await websocket.send_json({
                    "type": "VULNERABILITY_FOUND",
                    "data": {
                        "id": vuln.vulnerability_id,
                        "severity": vuln.severity,
                        "title": vuln.title,
                        "description": vuln.description,
                        "agent": vuln.agent_name,
                        "domain": vuln.domain,
                        "confidence": vuln.confidence,
                    },
                })
                await asyncio.sleep(0.05)

        # Emit patches applied in this iteration
        iter_patch_ids = set(summary.patches_applied)
        for patch in final_state.patches:
            if patch.patch_id in iter_patch_ids:
                await websocket.send_json({
                    "type": "PATCH_APPLIED",
                    "data": {
                        "id": patch.patch_id,
                        "target_vulnerability_id": patch.target_vulnerability_id,
                        "description": patch.fix_description,
                        "confidence": patch.patch_confidence,
                        "full_fix": not (isinstance(patch, IncrementalPatch) and not patch.full_fix),
                    },
                })
                await asyncio.sleep(0.05)

        # Security score after this iteration
        if len(final_state.security_scores) >= current_iter:
            await websocket.send_json({
                "type": "SCORE_UPDATE",
                "data": final_state.security_scores[current_iter - 1],
            })

    # Judge decision
    await websocket.send_json({
        "type": "JUDGE_DECISION",
        "data": {
            "decision": final_state.status,
            "reason": final_state.termination_reason or "",
        },
    })

    # Final summary
    if final_state.attack_effectiveness is not None:
        await websocket.send_json({
            "type": "ATTACK_EFFECTIVENESS_UPDATE",
            "data": final_state.attack_effectiveness,
        })

    if final_state.defense_quality is not None:
        await websocket.send_json({
            "type": "DEFENSE_QUALITY_UPDATE",
            "data": final_state.defense_quality,
        })

    if final_state.convergence_metrics is not None:
        await websocket.send_json({
            "type": "CONVERGENCE_UPDATE",
            "data": final_state.convergence_metrics,
        })

    await websocket.send_json({
        "type": "SIMULATION_END",
        "data": {
            "status": final_state.status,
            "total_vulnerabilities": len(final_state.vulnerabilities),
            "total_patches": len(final_state.patches),
            "iterations": final_state.iteration_count,
            "security_score": final_state.current_security_score,
            "attack_effectiveness": final_state.attack_effectiveness,
            "defense_quality": final_state.defense_quality,
            "convergence_metrics": final_state.convergence_metrics,
        },
    })


@app.websocket("/ws/simulate")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time simulation streaming.
    
    Protocol:
    1. Client connects
    2. Client sends START_SIMULATION message with prompt
    3. Server streams events in real-time
    4. Server sends SIMULATION_END when complete
    """
    await websocket.accept()
    logger.info("WebSocket connection established")
    client_key = _websocket_client_identity(websocket)
    
    try:
        # Wait for start message from client
        _enforce_ws_rate_limit(client_key, "connect", _WS_MAX_CONNECTS)
        data = await asyncio.wait_for(websocket.receive_json(), timeout=_WS_HANDSHAKE_TIMEOUT_SECONDS)
        _enforce_ws_rate_limit(client_key, "message", _WS_MAX_ACTIONS)
        
        if data.get("type") == "SUBSCRIBE_RUN":
            _enforce_websocket_access(websocket)
            run_id = data.get("data", {}).get("run_id", "")
            run_token = data.get("data", {}).get("run_token", "")
            if not run_id:
                await websocket.send_json({
                    "type": "ERROR",
                    "data": {"message": "Missing run_id for SUBSCRIBE_RUN"},
                })
                return
            run = get_run(run_id)
            if not run:
                await websocket.send_json({"type": "ERROR", "data": {"message": "run_not_found"}})
                return

            provided_run_token = run_token or websocket.headers.get("x-run-token", "")
            _enforce_run_owner_access(run, provided_run_token)
            await _stream_run_subscription(websocket, run_id)
            return

        if data.get("type") != "START_SIMULATION":
            await websocket.send_json({
                "type": "ERROR",
                "data": {"message": "Expected START_SIMULATION message"}
            })
            return
        
        prompt = data.get("data", {}).get("prompt", "")
        config = data.get("data", {}).get("config", {})
        use_mock = data.get("data", {}).get("use_mock", True)
        demo_id = data.get("data", {}).get("demo_id")

        if not use_mock:
            _enforce_live_run_websocket_access(websocket)
        
        logger.info(f"Starting simulation: prompt='{prompt[:50]}...', mock={use_mock}")
        
        # Send initial event
        await websocket.send_json({
            "type": "SYSTEM_INIT",
            "data": {
                "prompt": prompt,
                "config": config,
                "timestamp": asyncio.get_event_loop().time()
            }
        })
        
        if use_mock:
            if demo_id and demo_id in DEMO_RUNS:
                for event in DEMO_RUNS[demo_id]["events"]:
                    await websocket.send_json(event)
                    await asyncio.sleep(0.2)
            else:
                # Use mock data for development
                await send_mock_simulation(websocket, prompt)
        else:
            await run_real_simulation(websocket, prompt, config or {})
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except TimeoutError:
        try:
            await websocket.send_json({"type": "ERROR", "data": {"message": "handshake_timeout"}})
        except Exception:
            pass
    except HTTPException as exc:
        try:
            await websocket.send_json({
                "type": "ERROR",
                "data": {"message": str(exc.detail)},
            })
        except Exception:
            pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "ERROR",
                "data": {"message": "websocket_error"}
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
        logger.info("WebSocket connection closed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
