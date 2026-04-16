"""
FastAPI WebSocket server for AI Crucible War Room Dashboard.

Provides real-time streaming of Crucible simulation events to frontend.
"""

import sys
from pathlib import Path

# Add the main package source to path so the backend venv can import crucible
_repo_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_repo_root / "src"))

# Load .env from repo root so API keys are available
from dotenv import load_dotenv
load_dotenv(_repo_root / ".env")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import logging

# Import mock server for development
from .mock_server import send_mock_simulation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Crucible API",
    description="Real-time WebSocket API for War Room Dashboard",
    version="1.0.0"
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
    
    try:
        # Wait for start message from client
        data = await websocket.receive_json()
        
        if data.get("type") != "START_SIMULATION":
            await websocket.send_json({
                "type": "ERROR",
                "data": {"message": "Expected START_SIMULATION message"}
            })
            return
        
        prompt = data.get("data", {}).get("prompt", "")
        config = data.get("data", {}).get("config", {})
        use_mock = data.get("data", {}).get("use_mock", True)
        
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
            # Use mock data for development
            await send_mock_simulation(websocket, prompt)
        else:
            await run_real_simulation(websocket, prompt, config or {})
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "ERROR",
                "data": {"message": str(e)}
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
