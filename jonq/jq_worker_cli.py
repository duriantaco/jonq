from __future__ import annotations
import json, subprocess, threading, atexit
from typing import Dict
from functools import lru_cache
import asyncio

class JQWorker:
    def __init__(self, filter_src: str):
        self.filter = filter_src
        self.proc = subprocess.Popen(
            ["jq", "-c", "--unbuffered", filter_src],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self._lock = threading.Lock()

    def query(self, obj) -> str:
        payload = json.dumps(obj, separators=(",", ":")) + "\n"
        with self._lock:                   
            self.proc.stdin.write(payload)
            self.proc.stdin.flush()
            return self.proc.stdout.readline().rstrip("\n")

    def close(self):
        self.proc.terminate()

_workers: Dict[str, JQWorker] = {}

@lru_cache(maxsize=32)
def get_worker(filter_src: str) -> "JQWorker":
    if (w := _workers.get(filter_src)) and w.proc.poll() is None:
        return w
    _workers[filter_src] = JQWorker(filter_src)
    return _workers[filter_src]

##### for async support #####
class AsyncJQWorker:
    def __init__(self, filter_src: str):
        self.filter = filter_src
        self.proc = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the jq process"""
        self.proc = await asyncio.create_subprocess_exec(
            "jq", "-c", "--unbuffered", self.filter,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, 
            text=False
        )

    async def query(self, obj) -> str:
        if not self.proc:
            await self.start()
            
        payload = json.dumps(obj, separators=(",", ":")) + "\n"
        async with self._lock:
            self.proc.stdin.write(payload.encode())
            await self.proc.stdin.drain()
            result = await self.proc.stdout.readline()
            return result.decode().rstrip("\n")

    async def close(self):
        if self.proc:
            self.proc.terminate()
            await self.proc.wait()

_async_workers: Dict[tuple, AsyncJQWorker] = {}

async def get_worker_async(filter_src: str) -> "AsyncJQWorker":
    current_loop = asyncio.get_running_loop()
    
    cache_key = (filter_src, id(current_loop))
    
    if cache_key in _async_workers:
        worker = _async_workers[cache_key]
        if worker.proc and worker.proc.returncode is None:
            return worker
    
    worker = AsyncJQWorker(filter_src)
    await worker.start()
    _async_workers[cache_key] = worker
    return worker

async def _cleanup_async():
    """Cleanup async workers"""
    for w in _async_workers.values():
        try:
            await w.close()
        except Exception:
            pass

def _cleanup():
    """Cleanup sync workers"""
    for w in _workers.values():
        try:
            w.close()
        except Exception:
            pass
    
    try:
        loop = asyncio.get_running_loop()
        if loop and not loop.is_closed():
            loop.create_task(_cleanup_async())
    except RuntimeError:
        try:
            asyncio.run(_cleanup_async())
        except Exception:
            pass

atexit.register(_cleanup)