"""Shared application state and utilities for the agent service."""

import os
from typing import Dict, Optional
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
    "get_task",
    "set_task",
    "delete_task",
    "get_idempotency_key",
    "set_idempotency_key",
    "get_task_retries",
    "set_task_retries",
    "increment_task_retries",
    "get_run",
    "set_run",
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


# In-memory fallback for task state (when Redis not available)
_tasks: Dict[str, dict] = {}
_idempotency_keys: Dict[str, str] = {}
_task_retries: Dict[str, int] = {}

# Redis key prefixes
TASK_KEY_PREFIX = "saea:task:"
IDEMPOTENCY_KEY_PREFIX = "saea:idempotency:"
TASK_RETRIES_KEY_PREFIX = "saea:retries:"
RUN_KEY_PREFIX = "saea:run:"


def _get_redis():
    """Get Redis client if available."""
    return get_redis_client()


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def _idempotency_key(key: str) -> str:
    return f"{IDEMPOTENCY_KEY_PREFIX}{key}"


def _retries_key(task_id: str) -> str:
    return f"{TASK_RETRIES_KEY_PREFIX}{task_id}"


def get_task(task_id: str) -> Optional[dict]:
    """Get task state from Redis or in-memory fallback."""
    r = _get_redis()
    if r:
        try:
            import json

            data = r.hgetall(_task_key(task_id))
            if data:
                return {k: json.loads(v) for k, v in data.items()}
        except Exception:
            pass
    return _tasks.get(task_id)


def set_task(task_id: str, data: dict) -> None:
    """Set task state in Redis or in-memory fallback."""
    r = _get_redis()
    if r:
        try:
            import json

            pipe = r.pipeline()
            for k, v in data.items():
                pipe.hset(_task_key(task_id), k, json.dumps(v))
            # Set TTL for 24 hours
            pipe.expire(_task_key(task_id), 86400)
            pipe.execute()
            return
        except Exception:
            pass
    _tasks[task_id] = data


def delete_task(task_id: str) -> None:
    """Delete task state from Redis or in-memory fallback."""
    r = _get_redis()
    if r:
        try:
            r.delete(_task_key(task_id))
            return
        except Exception:
            pass
    _tasks.pop(task_id, None)


def get_idempotency_key(key: str) -> Optional[str]:
    """Get task_id from idempotency key."""
    r = _get_redis()
    if r:
        try:
            return r.get(_idempotency_key(key))
        except Exception:
            pass
    return _idempotency_keys.get(key)


def set_idempotency_key(key: str, task_id: str) -> None:
    """Set idempotency key mapping."""
    r = _get_redis()
    if r:
        try:
            r.setex(_idempotency_key(key), 86400, task_id)
            return
        except Exception:
            pass
    _idempotency_keys[key] = task_id


def get_task_retries(task_id: str) -> int:
    """Get task retry count."""
    r = _get_redis()
    if r:
        try:
            val = r.get(_retries_key(task_id))
            if val is not None:
                return int(val)
        except Exception:
            pass
    return _task_retries.get(task_id, 0)


def set_task_retries(task_id: str, count: int) -> None:
    """Set task retry count."""
    r = _get_redis()
    if r:
        try:
            r.setex(_retries_key(task_id), 86400, str(count))
            return
        except Exception:
            pass
    _task_retries[task_id] = count


def increment_task_retries(task_id: str) -> int:
    """Increment and return task retry count."""
    r = _get_redis()
    if r:
        try:
            val = r.incr(_retries_key(task_id))
            r.expire(_retries_key(task_id), 86400)
            return val
        except Exception:
            pass
    count = _task_retries.get(task_id, 0) + 1
    _task_retries[task_id] = count
    return count


def _run_key(run_id: str) -> str:
    return f"{RUN_KEY_PREFIX}{run_id}"


# In-memory fallback for run data (when Redis not available)
_runs: Dict[str, dict] = {}


def get_run(run_id: str) -> Optional[dict]:
    """Get run data from Redis or in-memory fallback."""
    r = _get_redis()
    if r:
        try:
            import json

            data = r.hgetall(_run_key(run_id))
            if data:
                return {k: json.loads(v) for k, v in data.items()}
        except Exception:
            pass
    return _runs.get(run_id)


def set_run(run_id: str, data: dict) -> None:
    """Set run data in Redis or in-memory fallback."""
    r = _get_redis()
    if r:
        try:
            import json

            pipe = r.pipeline()
            for k, v in data.items():
                pipe.hset(_run_key(run_id), k, json.dumps(v))
            # Set TTL for 7 days (longer than tasks since runs may be referenced later)
            pipe.expire(_run_key(run_id), 604800)
            pipe.execute()
            return
        except Exception:
            pass
    _runs[run_id] = data
