"""Background queue and pubsub utilities for run execution."""

from __future__ import annotations

import json
import os

from celery import Celery
import redis


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("crucible", broker=REDIS_URL, backend=REDIS_URL)


def redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def publish_run_event(run_id: str, event: dict) -> None:
    channel = f"run:{run_id}:events"
    redis_client().publish(channel, json.dumps(event))
