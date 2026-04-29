import json
import logging
import os

from jonq.jq_worker_cli import get_worker, get_worker_async
from jonq.stream_utils import (
    process_json_streaming_inline,
    process_json_streaming_inline_async,
)
import aiofiles

logger = logging.getLogger(__name__)


def _filter_emits_multiple_values(jq_filter: str) -> bool:
    stripped = jq_filter.lstrip()
    return stripped.startswith(".[]") or stripped.startswith(".[]?")


def _run_jq_raw(jq_filter, json_text):
    try:
        worker = get_worker(jq_filter)
        out = worker.query(json.loads(json_text))
        return out, ""
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON: {exc}"
    except Exception as exc:
        return "", f"Error in jq filter: {exc}"


def run_jq(arg1, arg2):
    if os.path.exists(arg1):
        json_path, jq_filter = arg1, arg2
        try:
            with open(json_path, "r", encoding="utf-8") as fp:
                json_txt = fp.read()
        except (OSError, IOError) as exc:
            raise FileNotFoundError(f"Cannot read JSON file: {exc}") from exc

        out, err = _run_jq_raw(jq_filter, json_txt)
        if err:
            if err.startswith("Invalid JSON"):
                raise ValueError(err)
            raise ValueError(f"Error in jq filter: {err}")
        return out, err

    return _run_jq_raw(arg1, arg2)


def run_jq_streaming(json_file, jq_filter, chunk_size=1000):
    emits_objects = _filter_emits_multiple_values(jq_filter)
    wrapper = f"[{jq_filter}]" if emits_objects else jq_filter

    def _process_chunk(chunk_json):
        stdout, stderr = run_jq(wrapper, chunk_json)
        if stderr:
            raise RuntimeError(stderr)
        return stdout

    try:
        merged_json = process_json_streaming_inline(
            json_file, _process_chunk, chunk_size=chunk_size
        )
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


async def _run_jq_raw_async(jq_filter, json_text):
    try:
        worker = await get_worker_async(jq_filter)
        out = await worker.query(json.loads(json_text))
        return out, ""
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON: {exc}"
    except Exception as exc:
        return "", f"Error in jq filter: {exc}"


async def run_jq_async(arg1, arg2):
    if os.path.exists(arg1):
        json_path, jq_filter = arg1, arg2
        try:
            async with aiofiles.open(json_path, "r", encoding="utf-8") as fp:
                json_txt = await fp.read()
        except (OSError, IOError) as exc:
            raise FileNotFoundError(f"Cannot read JSON file: {exc}") from exc

        out, err = await _run_jq_raw_async(jq_filter, json_txt)
        if err:
            if err.startswith("Invalid JSON"):
                raise ValueError(err)
            raise ValueError(f"Error in jq filter: {err}")
        return out, err

    return await _run_jq_raw_async(arg1, arg2)


async def run_jq_streaming_async(json_file, jq_filter, chunk_size=1000):
    emits_objects = _filter_emits_multiple_values(jq_filter)
    wrapper = f"[{jq_filter}]" if emits_objects else jq_filter

    async def _process_chunk_async(chunk_json):
        stdout, stderr = await run_jq_async(wrapper, chunk_json)
        if stderr:
            raise RuntimeError(stderr)
        return stdout

    try:
        merged_json = await process_json_streaming_inline_async(
            json_file, _process_chunk_async, chunk_size=chunk_size
        )
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
