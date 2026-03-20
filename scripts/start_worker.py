import glob
import logging
import os
import signal
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prometheus_client import CollectorRegistry, multiprocess, start_http_server

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.workers.manager import WorkerManager

logger = logging.getLogger(__name__)


def _prepare_multiprocess_metrics_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    for metric_file in glob.glob(os.path.join(path, "*.db")):
        try:
            os.remove(metric_file)
        except OSError:
            logger.warning("Failed to remove stale Prometheus multiprocess file.", extra={"file": metric_file})


if __name__ == "__main__":
    setup_logging()
    settings = get_settings()

    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = multiproc_dir
    _prepare_multiprocess_metrics_dir(multiproc_dir)

    # Expose a single aggregated worker metrics endpoint for all worker child processes.
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    start_http_server(8001, registry=registry)

    manager = WorkerManager(num_workers=settings.num_workers)
    manager.start()

    shutdown_flag = {"value": False}

    def _request_shutdown(signum=None, frame=None):
        logger.info("Worker supervisor shutdown requested.", extra={"signal": signum})
        shutdown_flag["value"] = True

    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    try:
        while not shutdown_flag["value"]:
            if manager.alive_count == 0:
                logger.warning("All worker processes exited; stopping supervisor.")
                break
            time.sleep(1.0)
    finally:
        manager.stop(grace_period=30.0)