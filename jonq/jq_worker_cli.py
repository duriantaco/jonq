from __future__ import annotations

import asyncio
from functools import lru_cache
import json
import subprocess

from jonq.constants import WORKER_CACHE_SIZE


def _command(filter_src: str) -> list[str]:
    # A filter such as -1 must be passed as jq source, rather than an option.
    return ["jq", "-c", f" {filter_src}"]


def _result(stdout: bytes, stderr: bytes, returncode: int) -> str:
    if returncode:
        error = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(error or f"jq exited with status {returncode}")
    return stdout.decode("utf-8").replace("\r\n", "\n").rstrip("\n")


class JQWorker:
    """Run a filter against one complete input document at a time."""

    def __init__(self, filter_src: str):
        self.filter = filter_src

    def query(self, obj) -> str:
        return self.query_text(json.dumps(obj, separators=(",", ":")))

    def query_text(self, json_text: str) -> str:
        process = subprocess.run(
            _command(self.filter), input=json_text.encode("utf-8"), capture_output=True,
        )
        return _result(process.stdout, process.stderr, process.returncode)


class AsyncJQWorker:
    """Run one jq process per async query and reap it before returning."""

    def __init__(self, filter_src: str):
        self.filter = filter_src

    async def query(self, obj) -> str:
        return await self.query_text(json.dumps(obj, separators=(",", ":")))

    async def query_text(self, json_text: str) -> str:
        payload = json_text.encode("utf-8")
        process = await asyncio.create_subprocess_exec(
            *_command(self.filter),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        communication = asyncio.create_task(process.communicate(payload))
        try:
            stdout, stderr = await asyncio.shield(communication)
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await communication
            raise
        return _result(stdout, stderr, process.returncode)


@lru_cache(maxsize=WORKER_CACHE_SIZE)
def get_worker(filter_src: str) -> JQWorker:
    return JQWorker(filter_src)


@lru_cache(maxsize=WORKER_CACHE_SIZE)
def _get_async_worker(filter_src: str) -> AsyncJQWorker:
    return AsyncJQWorker(filter_src)


async def get_worker_async(filter_src: str) -> AsyncJQWorker:
    return _get_async_worker(filter_src)


def _cleanup() -> None:
    get_worker.cache_clear()
    _get_async_worker.cache_clear()


async def _cleanup_async() -> None:
    _get_async_worker.cache_clear()
