import multiprocessing
import os


def _worker_target(database_url: str, redis_url: str, max_iterations, failure_rate: float):
    os.environ["DATABASE_URL"] = database_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["SIMULATED_FAILURE_RATE"] = str(failure_rate)

    from app.workers.worker import process_jobs
    process_jobs(max_iterations=max_iterations)


class WorkerManager:
    def __init__(self, num_workers: int = None, max_iterations: int = None):
        from app.core.config import get_settings
        settings = get_settings()

        self.num_workers = num_workers if num_workers is not None else settings.num_workers
        self.max_iterations = max_iterations
        self._processes: list[multiprocessing.Process] = []

    def start(self):
        from app.core.config import get_settings
        settings = get_settings()

        for i in range(self.num_workers):
            p = multiprocessing.Process(
                target=_worker_target,
                args=(
                    settings.database_url,
                    settings.redis_url,
                    self.max_iterations,
                    settings.simulated_failure_rate,
                ),
                daemon=True,
                name=f"djps-worker-{i}",
            )
            p.start()
            self._processes.append(p)

    def stop(self):
        for p in self._processes:
            if p.is_alive():
                p.terminate()
        for p in self._processes:
            p.join(timeout=5)
        self._processes.clear()

    def join(self, timeout: float = None):
        for p in self._processes:
            p.join(timeout=timeout)

    @property
    def alive_count(self) -> int:
        return sum(1 for p in self._processes if p.is_alive())

    def __len__(self) -> int:
        return len(self._processes)
