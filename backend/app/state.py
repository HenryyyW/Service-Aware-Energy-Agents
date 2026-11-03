"""Shared application state and utilities for the agent service."""

import os
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge

try:
    import redis
    from rq import Queue, Worker
    from rq.job import Job

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

__all__ = [
    "REDIS_AVAILABLE",
    "TASK_DURATION",
    "TASKS_TOTAL",
    "TASK_QUEUE_SIZE",
    "LLM_TOKENS_TOTAL",
    "LLM_COST_TOTAL",
    "TASK_RETRIES",
    "get_redis_client",
    "get_task_queue",
    "get_job",
]

# Prometheus metrics
TASK_DURATION = Histogram(
    "agent_task_duration_seconds", "Agent task duration in seconds", ["status"]
)
TASKS_TOTAL = Counter("agent_tasks_total", "Total agent tasks", ["status"])
TASK_QUEUE_SIZE = Gauge("agent_task_queue_size", "Number of tasks in queue")
LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total", "Total LLM tokens used", ["model", "type"]
)
LLM_COST_TOTAL = Counter("llm_cost_usd_total", "Total LLM cost in USD", ["model"])
TASK_RETRIES = Counter("agent_task_retries_total", "Total task retries", ["task_id"])

# Redis/RQ setup
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = None
task_queue = None


def get_redis_client():
    """Get or create Redis client with connection pooling."""
    global redis_client
    if redis_client is None and REDIS_AVAILABLE:
        try:
            import redis

            redis_client = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            redis_client.ping()
        except Exception:
            redis_client = None
    return redis_client


def get_task_queue():
    """Get or create RQ task queue."""
    global task_queue
    if task_queue is None:
        try:
            import redis
            from rq import Queue

            client = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            client.ping()
            task_queue = Queue("agent_tasks", connection=client)
        except Exception:
            return None
    return task_queue


def get_job(task_id: str):
    """Fetch a job by ID."""
    try:
        from rq.job import Job
    except ImportError:
        return None
    client = get_redis_client()
    if client:
        try:
            from rq import Queue

            q = Queue(
                "agent_tasks",
                connection=redis.from_url(
                    os.getenv("REDIS_URL", "redis://localhost:6379/0")
                ),
            )
            return Job.fetch(task_id, connection=q.connection)
        except Exception:
            return None
    return None
