"""
Threaded pipeline dispatch — runs the analysis pipeline in a background thread
and publishes progress to the cache so the frontend can poll.
"""
import gc
import uuid
import threading
import traceback
import logging

from cache.redis_cache import cache

logger = logging.getLogger(__name__)

# In-memory store for completed results (supplements Redis)
_results: dict = {}

# ── Concurrency guard ────────────────────────────────────────────────────────
# Only 1 pipeline runs at a time on this process.
# A second upload while one is running gets a 429 immediately — this prevents
# multiple DataFrames from stacking up in RAM and crashing the server.
_pipeline_semaphore = threading.Semaphore(1)
_active_job_id: str | None = None


def is_pipeline_busy() -> bool:
    """Return True if a pipeline job is currently running."""
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
    cache.set_job_status(job_id, "queued", step="Waiting...", progress=0)

    def _run():
        global _active_job_id
        try:
            from core.coordinator import PipelineCoordinator
            coordinator = PipelineCoordinator()

            def on_step(agent_name, index, total):
                pct = round(index / total, 2)
                cache.set_job_status(job_id, "running", step=agent_name, progress=pct)

            result = coordinator.run(df, on_step=on_step)

            cache.set_job_status(job_id, "done", step="Done", progress=1.0)
            _results[job_id] = result

        except Exception as e:
            logger.exception("Pipeline failed for job %s", job_id)
            cache.set_job_status(job_id, "error", step=str(e), progress=0)

        finally:
            # ── Explicit cleanup: release DataFrame RAM immediately ──────────
            # Without this, the df reference lives until GC decides to collect.
            # On a 512 MB free-tier instance this is the difference between
            # staying alive and being OOM-killed on the next request.
            try:
                del df
            except Exception:
                pass
            gc.collect()
            _active_job_id = None
            _pipeline_semaphore.release()
            logger.info("Pipeline slot released (job=%s)", job_id)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return job_id


def get_result(job_id: str):
    return _results.pop(job_id, None)

