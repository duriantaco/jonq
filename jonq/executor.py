import json
import logging
from typing import Tuple
import subprocess 

from jonq.jq_worker_cli import get_worker
from jonq.stream_utils import process_json_streaming

logger = logging.getLogger(__name__)

def _run_jq_raw(jq_filter: str, json_text: str) -> Tuple[str, str]:
    try:
        worker = get_worker(jq_filter)
        out = worker.query(json.loads(json_text))
        return out, ""
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON: {exc}"
    except Exception as exc:
        return "", f"Error in jq filter: {exc}"

def run_jq(json_file: str, jq_filter: str) -> Tuple[str, str]:
    """
    Execute `jq_filter` against the JSON contained in `json_file`.
    Returns (stdout, stderr).  Raises ValueError for malformed JSON
    and for jq compilation/runtime errors so the tests can `pytest.raises`.
    """
    try:
        with open(json_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    proc = subprocess.run(
        ["jq", "-c", jq_filter],
        input=json.dumps(data, separators=(",", ":")),
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        raise ValueError(f"Error in jq filter: {proc.stderr.strip()}")

    return proc.stdout.strip(), ""

def run_jq_streaming(json_file: str,
                     jq_filter: str,
                     chunk_size: int = 1000) -> Tuple[str, str]:
    emits_objects = jq_filter.startswith(".[]") or "| .[" in jq_filter
    wrapper = f"[{jq_filter}]" if emits_objects else jq_filter

    def _process_chunk(chunk_path: str) -> str:
        with open(chunk_path, "r", encoding="utf-8") as fp:
            chunk_json = fp.read()
        stdout, stderr = run_jq(wrapper, chunk_json)
        if stderr:
            raise RuntimeError(stderr)
        return stdout

    try:
        merged_json = process_json_streaming(json_file,
                                             _process_chunk,
                                             chunk_size=chunk_size)
    except Exception as exc:
        logger.error("Streaming execution error: %s", exc)
        return "", f"Streaming execution error: {exc}"

    # for the .[] filters normalise the final output to single flat array
    if emits_objects:
        try:
            data = json.loads(merged_json)
            if not isinstance(data, list):
                data = [data]
            merged_json = json.dumps(data, separators=(",", ":"))
        except json.JSONDecodeError as exc:
            return "", f"Error parsing results: {exc}"

    return merged_json, ""
