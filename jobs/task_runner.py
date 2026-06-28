"""
Threaded pipeline dispatch — runs the analysis pipeline in a background thread
and publishes progress to the cache so the frontend can poll.
"""
import uuid
import threading
import traceback
import logging

from cache.redis_cache import cache
from core.coordinator import PipelineCoordinator

logger = logging.getLogger(__name__)

# In-memory store for completed results (supplements Redis)
_results: dict = {}


def dispatch_pipeline(df, analysis_id: str = None) -> str:
    """
    Launch the pipeline in a background thread.
    Returns a job_id immediately so the client can poll for progress.
    """
    job_id = analysis_id or str(uuid.uuid4())

    cache.set_job_status(job_id, "queued", step="Waiting...", progress=0)

    def _run():
        try:
            coordinator = PipelineCoordinator()

            def on_step(agent_name, index, total):
                pct = round(index / total, 2)
                cache.set_job_status(job_id, "running", step=agent_name, progress=pct)

            result = coordinator.run(df, on_step=on_step)

            # Store only the serialisable parts
            cache.set_job_status(job_id, "done", step="Done", progress=1.0)
            _results[job_id] = result

        except Exception as e:
            logger.exception("Pipeline failed for job %s", job_id)
            cache.set_job_status(job_id, "error", step=str(e), progress=0)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return job_id


def get_result(job_id: str):
    return _results.pop(job_id, None)
