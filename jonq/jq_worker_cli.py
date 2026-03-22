from __future__ import annotations
import atexit
import json
import logging
import selectors
import subprocess
import threading
from collections import OrderedDict
import asyncio
from jonq.constants import WORKER_CACHE_SIZE

logger = logging.getLogger(__name__)


class JQWorker:
    def __init__(self, filter_src):
        self.filter = filter_src
        self.proc = subprocess.Popen(
            ["jq", "-c", "--unbuffered", filter_src],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()

    def is_alive(self):
        return self.proc.poll() is None

    def _read_stderr(self):
        if not self.proc.stderr:
            return ""
        return self.proc.stderr.read().strip()

    def query(self, obj):
        if not self.is_alive():
            raise RuntimeError(self._read_stderr() or "jq worker exited unexpectedly")

        payload = json.dumps(obj, separators=(",", ":")) + "\n"
        with self._lock:
            try:
                self.proc.stdin.write(payload)
                self.proc.stdin.flush()
            except BrokenPipeError as exc:
                raise RuntimeError(
                    self._read_stderr() or "jq worker exited unexpectedly"
                ) from exc

            selector = selectors.DefaultSelector()
            selector.register(self.proc.stdout, selectors.EVENT_READ)
            selector.register(self.proc.stderr, selectors.EVENT_READ)
            try:
                while True:
                    events = selector.select(timeout=1)
                    if not events:
                        if not self.is_alive():
                            raise RuntimeError(
                                self._read_stderr() or "jq worker exited unexpectedly"
                            )
                        continue

                    ready = {key.fileobj for key, _ in events}

                    if self.proc.stdout in ready:
                        result = self.proc.stdout.readline()
                        if result != "":
                            return result.rstrip("\n")
                        if not self.is_alive():
                            raise RuntimeError(
                                self._read_stderr() or "jq worker exited unexpectedly"
                            )

                    if self.proc.stderr in ready:
                        error = self.proc.stderr.readline().strip()
                        if error:
                            raise RuntimeError(error)
                        if not self.is_alive():
                            raise RuntimeError(
                                self._read_stderr() or "jq worker exited unexpectedly"
                            )
            finally:
                selector.close()

    def close(self):
        if self.is_alive():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


_workers: OrderedDict[str, JQWorker] = OrderedDict()


def _trim_worker_cache():
    while len(_workers) > WORKER_CACHE_SIZE:
        _, worker = _workers.popitem(last=False)
        try:
            worker.close()
        except (OSError, RuntimeError):
            logger.debug("Failed to close evicted jq worker")


def get_worker(filter_src):
    worker = _workers.get(filter_src)
    if worker is not None:
        if worker.is_alive():
            _workers.move_to_end(filter_src)
            return worker
        _workers.pop(filter_src, None)
        try:
            worker.close()
        except (OSError, RuntimeError):
            logger.debug("Failed to close stale jq worker")

    worker = JQWorker(filter_src)
    _workers[filter_src] = worker
    _trim_worker_cache()
    return worker


class AsyncJQWorker:
    def __init__(self, filter_src):
        self.filter = filter_src
        self.proc = None
        self._lock = asyncio.Lock()

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            "jq",
            "-c",
            "--unbuffered",
            self.filter,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=False,
        )

    def is_alive(self):
        return self.proc is not None and self.proc.returncode is None

    async def _read_stderr(self):
        if not self.proc or not self.proc.stderr:
            return ""
        stderr = await self.proc.stderr.read()
        return stderr.decode().strip()

    async def query(self, obj):
        if not self.proc:
            await self.start()
        elif not self.is_alive():
            raise RuntimeError(await self._read_stderr() or "jq worker exited unexpectedly")

        payload = json.dumps(obj, separators=(",", ":")) + "\n"
        async with self._lock:
            try:
                self.proc.stdin.write(payload.encode())
                await self.proc.stdin.drain()
            except BrokenPipeError as exc:
                raise RuntimeError(
                    await self._read_stderr() or "jq worker exited unexpectedly"
                ) from exc

            stdout_task = asyncio.create_task(self.proc.stdout.readline())
            stderr_task = asyncio.create_task(self.proc.stderr.readline())
            try:
                done, pending = await asyncio.wait(
                    {stdout_task, stderr_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

                result = stdout_task.result() if stdout_task in done else b""
                error = stderr_task.result() if stderr_task in done else b""

                if result:
                    return result.decode().rstrip("\n")
                if error:
                    raise RuntimeError(error.decode().strip())
                if not self.is_alive():
                    raise RuntimeError(
                        await self._read_stderr() or "jq worker exited unexpectedly"
                    )
                raise RuntimeError("jq worker produced no output")
            finally:
                for task in (stdout_task, stderr_task):
                    if not task.done():
                        task.cancel()

    async def close(self):
        if self.is_alive():
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=1)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()


_async_workers: OrderedDict[tuple[str, int], AsyncJQWorker] = OrderedDict()
_patched_loops: set[int] = set()


async def _trim_async_worker_cache():
    while len(_async_workers) > WORKER_CACHE_SIZE:
        _, worker = _async_workers.popitem(last=False)
        try:
            await worker.close()
        except (OSError, RuntimeError):
            logger.debug("Failed to close evicted async jq worker")


async def _close_async_workers(workers):
    for worker in workers:
        try:
            await worker.close()
        except (OSError, RuntimeError):
            logger.debug("Failed to close async worker during cleanup")


def _pop_async_workers_for_loop(loop_id: int):
    cache_keys = [key for key in _async_workers if key[1] == loop_id]
    workers = []
    for cache_key in cache_keys:
        workers.append(_async_workers.pop(cache_key))
    return workers


def _ensure_loop_cleanup(loop):
    loop_id = id(loop)
    if loop_id in _patched_loops:
        return

    original_close = loop.close

    def close_with_worker_cleanup():
        workers = _pop_async_workers_for_loop(loop_id)
        if workers and not loop.is_closed() and not loop.is_running():
            loop.run_until_complete(_close_async_workers(workers))
        return original_close()

    loop.close = close_with_worker_cleanup
    _patched_loops.add(loop_id)


async def get_worker_async(filter_src):
    current_loop = asyncio.get_running_loop()
    _ensure_loop_cleanup(current_loop)
    cache_key = (filter_src, id(current_loop))

    if cache_key in _async_workers:
        worker = _async_workers[cache_key]
        if worker.is_alive():
            _async_workers.move_to_end(cache_key)
            return worker
        _async_workers.pop(cache_key, None)
        try:
            await worker.close()
        except (OSError, RuntimeError):
            logger.debug("Failed to close stale async jq worker")

    worker = AsyncJQWorker(filter_src)
    await worker.start()
    _async_workers[cache_key] = worker
    await _trim_async_worker_cache()
    return worker


async def _cleanup_async():
    workers = list(_async_workers.values())
    _async_workers.clear()
    await _close_async_workers(workers)


def _cleanup():
    workers = list(_workers.values())
    _workers.clear()
    for w in workers:
        try:
            w.close()
        except (OSError, RuntimeError):
            logger.debug("Failed to close worker during cleanup")

    try:
        loop = asyncio.get_running_loop()
        if loop and not loop.is_closed():
            loop.create_task(_cleanup_async())
    except RuntimeError:
        try:
            asyncio.run(_cleanup_async())
        except (OSError, RuntimeError):
            logger.debug("Failed to run async cleanup")


atexit.register(_cleanup)
