from unittest.mock import MagicMock, patch

from app.workers.manager import WorkerManager


def _make_mock_process(alive=True):
    p = MagicMock()
    p.is_alive.return_value = alive
    return p


# Test 1: start() spawns the right number of subprocesses
def test_start_spawns_correct_number_of_processes():
    with patch("app.workers.manager.multiprocessing.Process") as MockProcess:
        mock_instances = [_make_mock_process() for _ in range(3)]
        MockProcess.side_effect = mock_instances

        manager = WorkerManager(num_workers=3, max_iterations=5)
        manager.start()

        assert MockProcess.call_count == 3
        for instance in mock_instances:
            instance.start.assert_called_once()

# Test 2: manager defaults to num_workers from settings
def test_manager_reads_num_workers_from_settings():
    with patch("app.workers.manager.multiprocessing.Process") as MockProcess:
        MockProcess.side_effect = [_make_mock_process() for _ in range(2)]

        manager = WorkerManager(max_iterations=5)
        manager.start()

        assert MockProcess.call_count == 2

# Test 3: stop() terminates every running process and waits with grace period
def test_stop_terminates_all_processes():
    with patch("app.workers.manager.multiprocessing.Process") as MockProcess:
        mock_instances = []
        for _ in range(2):
            p = MagicMock()
            p.is_alive.side_effect = [True, False]
            mock_instances.append(p)
        MockProcess.side_effect = mock_instances

        manager = WorkerManager(num_workers=2, max_iterations=5)
        manager.start()
        manager.stop(grace_period=5.0)

        for instance in mock_instances:
            instance.terminate.assert_called_once()
            instance.join.assert_called_once_with(timeout=5.0)
            instance.kill.assert_not_called()

        assert len(manager) == 0

# Test 4: stop() skips terminate() for processes that already exited
def test_stop_skips_dead_processes():
    with patch("app.workers.manager.multiprocessing.Process") as MockProcess:
        dead = _make_mock_process(alive=False)
        MockProcess.return_value = dead

        manager = WorkerManager(num_workers=1, max_iterations=5)
        manager.start()
        manager.stop()

        dead.terminate.assert_not_called()

# Test 5: alive_count reflects live processes
def test_alive_count():
    with patch("app.workers.manager.multiprocessing.Process") as MockProcess:
        alive = _make_mock_process(alive=True)
        dead = _make_mock_process(alive=False)
        MockProcess.side_effect = [alive, dead]

        manager = WorkerManager(num_workers=2, max_iterations=5)
        manager.start()

        assert manager.alive_count == 1

# Test 6: each process receives the correct env-var args
def test_worker_processes_receive_correct_args():
    with patch("app.workers.manager.multiprocessing.Process") as MockProcess:
        MockProcess.side_effect = [_make_mock_process() for _ in range(2)]

        manager = WorkerManager(num_workers=2, max_iterations=10)
        manager.start()

        for spawn_call in MockProcess.call_args_list:
            _, kwargs = spawn_call
            assert kwargs.get("daemon") is True
            args = kwargs.get("args", ())
            assert len(args) == 4
            database_url, redis_url, max_iter, _ = args
            assert "postgresql" in database_url
            assert "redis" in redis_url
            assert max_iter == 10

# Test 7: join() delegates to each process with the given timeout
def test_join_calls_join_on_each_process():
    with patch("app.workers.manager.multiprocessing.Process") as MockProcess:
        processes = [_make_mock_process() for _ in range(2)]
        MockProcess.side_effect = processes

        manager = WorkerManager(num_workers=2, max_iterations=5)
        manager.start()
        manager.join(timeout=3.0)

        for p in processes:
            p.join.assert_called_with(timeout=3.0)


# Test 8: _worker_target sets env vars and invokes process_jobs
def test_worker_target_calls_process_jobs():
    from app.workers.manager import _worker_target

    with patch("app.workers.worker.process_jobs") as mock_pj:
        _worker_target("postgresql://test/db", "redis://localhost:6379", 7, 0.0)

    mock_pj.assert_called_once_with(max_iterations=7)
