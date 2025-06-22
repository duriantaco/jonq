import json
import logging
from typing import Tuple
import os 

from jonq.jq_worker_cli import get_worker, get_worker_async
from jonq.stream_utils import process_json_streaming, process_json_streaming_async
import aiofiles

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


def run_jq(arg1: str, arg2: str) -> Tuple[str, str]:
    """
    Back-compat signature:
        run_jq(json_file_path, jq_filter)
    New signature (still accepted):
        run_jq(jq_filter, json_text)
    """
    if os.path.exists(arg1):
        json_path, jq_filter = arg1, arg2
        try:
            with open(json_path, "r", encoding="utf-8") as fp:
                json_txt = fp.read()
        except (OSError, IOError) as exc:
            raise FileNotFoundError(f"Cannot read JSON file: {exc}") from exc

        out, err = _run_jq_raw(jq_filter, json_txt)
        if err:
            raise ValueError(err)
        return out, err

    return _run_jq_raw(arg1, arg2)

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

async def _run_jq_raw_async(jq_filter: str, json_text: str) -> Tuple[str, str]:
    try:
        worker = await get_worker_async(jq_filter)
        out = await worker.query(json.loads(json_text))
        return out, ""
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON: {exc}"
    except Exception as exc:
        return "", f"Error in jq filter: {exc}"

async def run_jq_async(arg1: str, arg2: str) -> Tuple[str, str]:
    """
    Async version of run_jq
    Back-compat signature:
        run_jq_async(json_file_path, jq_filter)
    New signature (still accepted):
        run_jq_async(jq_filter, json_text)
    """
    if os.path.exists(arg1):
        json_path, jq_filter = arg1, arg2
        try:
            async with aiofiles.open(json_path, "r", encoding="utf-8") as fp:
                json_txt = await fp.read()
        except (OSError, IOError) as exc:
            raise FileNotFoundError(f"Cannot read JSON file: {exc}") from exc

        out, err = await _run_jq_raw_async(jq_filter, json_txt)
        if err:
            raise ValueError(err)
        return out, err

    return await _run_jq_raw_async(arg1, arg2)

async def run_jq_streaming_async(json_file: str,
                                jq_filter: str,
                                chunk_size: int = 1000) -> Tuple[str, str]:
    emits_objects = jq_filter.startswith(".[]") or "| .[" in jq_filter
    wrapper = f"[{jq_filter}]" if emits_objects else jq_filter

    async def _process_chunk_async(chunk_path: str) -> str:
        async with aiofiles.open(chunk_path, "r", encoding="utf-8") as fp:
            chunk_json = await fp.read()
        stdout, stderr = await run_jq_async(wrapper, chunk_json)
        if stderr:
            raise RuntimeError(stderr)
        return stdout

    try:
        merged_json = await process_json_streaming_async(json_file,
                                                        _process_chunk_async,
                                                        chunk_size=chunk_size)
    except Exception as exc:
        logger.error("Streaming execution error: %s", exc)
        return "", f"Streaming execution error: {exc}"

    if emits_objects:
        try:
            data = json.loads(merged_json)
            if not isinstance(data, list):
                data = [data]
            merged_json = json.dumps(data, separators=(",", ":"))
        except json.JSONDecodeError as exc:
            return "", f"Error parsing results: {exc}"

    return merged_json, ""
