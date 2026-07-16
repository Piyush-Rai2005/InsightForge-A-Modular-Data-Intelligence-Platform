"""
Threaded pipeline dispatch — runs the analysis pipeline in a background thread
and publishes progress to the cache so the frontend can poll.
"""
import gc
import uuid
import threading
import logging

from cache.redis_cache import cache

logger = logging.getLogger(__name__)

# In-memory store for completed results (supplements Redis)
_results: dict = {}

# ── Concurrency guard ────────────────────────────────────────────────────────
_pipeline_semaphore = threading.Semaphore(1)
_active_job_id: str | None = None

# ── Per-job cancellation events ──────────────────────────────────────────────
# Keyed by job_id. Set the event to request cancellation; the pipeline thread
# checks it between agents and raises CancelledError when it is set.
_cancel_events: dict[str, threading.Event] = {}


class JobCancelledError(Exception):
    """Raised inside the pipeline thread when a cancel is requested."""


def cancel_job(job_id: str) -> bool:
    """
    Signal the running pipeline to stop at the next agent boundary.
    Returns True if a cancel signal was sent, False if job not found.
    """
    event = _cancel_events.get(job_id)
    if event is None:
        return False
    event.set()
    cache.set_job_status(job_id, "cancelled", step="Cancelled by user", progress=0)
    logger.info("Cancel requested for job %s", job_id)
    return True


def is_pipeline_busy() -> bool:
    return not _pipeline_semaphore._value  # type: ignore[attr-defined]


def dispatch_pipeline(df, analysis_id: str = None) -> str:
    """
    Launch the pipeline in a background thread.
    Returns a job_id immediately so the client can poll for progress.
    Raises RuntimeError if a job is already running.
    """
    global _active_job_id

    if not _pipeline_semaphore.acquire(blocking=False):
        raise RuntimeError(
            f"A pipeline job is already running ({_active_job_id}). "
            "Please wait for it to finish before uploading a new file."
        )

    job_id = analysis_id or str(uuid.uuid4())
    _active_job_id = job_id

    cancel_event = threading.Event()
    _cancel_events[job_id] = cancel_event

    cache.set_job_status(job_id, "queued", step="Waiting...", progress=0)

    def _run():
        global _active_job_id
        try:
            from core.coordinator import PipelineCoordinator
            coordinator = PipelineCoordinator()

            def on_step(agent_name, index, total):
                # Check cancel flag before each agent starts
                if cancel_event.is_set():
                    raise JobCancelledError(f"Cancelled before {agent_name}")
                pct = round(index / total, 2)
                cache.set_job_status(job_id, "running", step=agent_name, progress=pct)

            result = coordinator.run(df, on_step=on_step)

            cache.set_job_status(job_id, "done", step="Done", progress=1.0)
            _results[job_id] = result

        except JobCancelledError:
            logger.info("Job %s was cancelled", job_id)
            cache.set_job_status(job_id, "cancelled", step="Cancelled by user", progress=0)

        except Exception as e:
            logger.exception("Pipeline failed for job %s", job_id)
            cache.set_job_status(job_id, "error", step=str(e), progress=0)

        finally:
            try:
                del df
            except Exception:
                pass
            gc.collect()
            _cancel_events.pop(job_id, None)
            _active_job_id = None
            _pipeline_semaphore.release()
            logger.info("Pipeline slot released (job=%s)", job_id)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return job_id


def get_result(job_id: str):
    return _results.pop(job_id, None)

