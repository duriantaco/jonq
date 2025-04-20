from __future__ import annotations
import json, subprocess, threading, atexit
from typing import Dict
from functools import lru_cache

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

def _cleanup():
    for w in _workers.values():
        try:
            w.close()
        except Exception:
            pass
atexit.register(_cleanup)
