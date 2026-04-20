"""Celery tasks for asynchronous simulation execution."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlmodel import Session

from crucible.graph import run_crucible

from .database import engine, RunRecord, RunEventRecord
from .queue import celery_app, publish_run_event

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="backend.run_simulation")
def run_simulation_task(run_id: str, prompt: str, config: dict | None = None) -> dict:
    del config  # reserved for future per-run provider/model overrides

    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if not run:
            return {"ok": False, "error": "run_not_found"}
        run.status = "running"
        run.started_at = utc_now()
        session.add(run)
        session.commit()

    publish_run_event(run_id, {"type": "RUN_STATUS", "data": {"status": "running"}})

    try:
        final_state = run_crucible(prompt)

        summary = {
            "status": final_state.status,
            "iterations": final_state.iteration_count,
            "total_vulnerabilities": len(final_state.vulnerabilities),
            "total_patches": len(final_state.patches),
            "security_score": final_state.current_security_score,
            "attack_effectiveness": final_state.attack_effectiveness,
            "defense_quality": final_state.defense_quality,
            "convergence_metrics": final_state.convergence_metrics,
        }

        event_payload = {"type": "SIMULATION_END", "data": summary}

        with Session(engine) as session:
            run = session.get(RunRecord, run_id)
            if run:
                run.status = "completed"
                run.completed_at = utc_now()
                run.summary_json = summary
                run.score = float(final_state.current_security_score or 0)
                run.grade = final_state.current_security_grade
                session.add(run)

            session.add(
                RunEventRecord(
                    run_id=run_id,
                    event_type="SIMULATION_END",
                    payload_json=summary,
                )
            )
            session.commit()

        publish_run_event(run_id, event_payload)
        return {"ok": True, "run_id": run_id}

    except Exception as exc:  # pragma: no cover
        logger.exception("Simulation task failed for run %s", run_id)
        safe_error = "simulation_failed"
        with Session(engine) as session:
            run = session.get(RunRecord, run_id)
            if run:
                run.status = "failed"
                run.completed_at = utc_now()
                run.error = safe_error
                session.add(run)
            session.add(
                RunEventRecord(
                    run_id=run_id,
                    event_type="ERROR",
                    payload_json={"message": safe_error},
                )
            )
            session.commit()

        publish_run_event(run_id, {"type": "ERROR", "data": {"message": safe_error}})
        return {"ok": False, "error": safe_error}
