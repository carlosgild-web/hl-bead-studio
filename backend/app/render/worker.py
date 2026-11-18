"""The single in-process render worker (decision 0003).

One daemon thread takes the oldest queued job, renders it and looks again; with nothing to
do it sleeps until `notify()` or the poll interval. One Blender at a time keeps a laptop's
CPU predictable. The FastAPI lifespan starts and stops it.
"""

import logging
import threading

from app.core.config import Settings
from app.render.jobs import next_queued, recover_interrupted, run_job

log = logging.getLogger(__name__)


class RenderWorker:
    def __init__(
        self,
        settings: Settings,
        *,
        poll_s: float = 2.0,
        command: list[str] | None = None,
    ):
        self.settings = settings
        self.poll_s = poll_s
        self.command = command  # tests swap Blender for a stand-in
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        recovered = recover_interrupted(self.settings)
        if recovered:
            log.warning("marked %d interrupted render job(s) as failed", recovered)
        self._thread = threading.Thread(target=self._loop, name="render-worker", daemon=True)
        self._thread.start()

    def notify(self) -> None:
        """A job was queued: look now instead of at the next poll."""
        self._wake.set()

    def stop(self, timeout: float = 5.0) -> None:
        """Ask the loop to end. A render in progress keeps running until Blender finishes
        or times out; if the process exits first, the next start marks the job failed."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run_pending(self) -> int:
        """Render every queued job now, in order. Returns how many were taken."""
        taken = 0
        while not self._stop.is_set() and (job_id := next_queued(self.settings)) is not None:
            if run_job(self.settings, job_id, command=self.command) is not None:
                taken += 1
        return taken

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()  # before looking, so a notify() during a render is not lost
            try:
                self.run_pending()
            except Exception:  # keep the worker alive; the job itself records its failure
                log.exception("render worker error")
            self._wake.wait(self.poll_s)
