from __future__ import annotations

import json
import os

import aiofiles

from jonq.jq_worker_cli import get_worker, get_worker_async
from jonq.json_utils import dumps
from jonq.stream_utils import (
    _extend_results,
    iter_json_array_chunks_async,
    merge_stream_results,
    process_json_streaming_inline,
)


def _filter_emits_multiple_values(jq_filter: str) -> bool:
    return jq_filter.lstrip().startswith(".[]")


def run_jq_text(jq_filter: str, json_text: str) -> tuple[str, str]:
    try:
        json.loads(json_text)
        return get_worker(jq_filter).query_text(json_text), ""
    except (json.JSONDecodeError, UnicodeError) as exc:
        return "", f"Invalid JSON: {exc}"
    except FileNotFoundError:
        return "", "jq is required. Install jq and make sure it is on PATH."
    except (OSError, RuntimeError) as exc:
        return "", f"Error in jq filter: {exc}"


def run_jq_file(json_path: str | os.PathLike, jq_filter: str) -> tuple[str, str]:
    try:
        with open(json_path, "r", encoding="utf-8") as source:
            json_text = source.read()
    except OSError as exc:
        raise FileNotFoundError(f"Cannot read JSON file: {exc}") from exc
    return run_jq_text(jq_filter, json_text)


def _is_file_argument(value: str | os.PathLike) -> bool:
    # Preserve both historical positional forms. A PathLike is unambiguous.
    return isinstance(value, os.PathLike) or os.path.isfile(value)


def run_jq(arg1, arg2):
    if _is_file_argument(arg1):
        out, error = run_jq_file(arg1, arg2)
        if error:
            raise ValueError(error)
        return out, error
    return run_jq_text(arg1, arg2)


def run_jq_streaming(json_file, jq_filter, chunk_size=1000):
    wrapper = f"[{jq_filter}]" if _filter_emits_multiple_values(jq_filter) else jq_filter

    def process_chunk(chunk_json):
        stdout, stderr = run_jq_text(wrapper, chunk_json)
        if stderr:
            raise RuntimeError(stderr)
        return stdout

    try:
        return process_json_streaming_inline(json_file, process_chunk, chunk_size=chunk_size), ""
    except Exception as exc:
        return "", f"Streaming execution error: {exc}"


async def run_jq_text_async(jq_filter: str, json_text: str) -> tuple[str, str]:
    try:
        json.loads(json_text)
        worker = await get_worker_async(jq_filter)
        return await worker.query_text(json_text), ""
    except (json.JSONDecodeError, UnicodeError) as exc:
        return "", f"Invalid JSON: {exc}"
    except FileNotFoundError:
        return "", "jq is required. Install jq and make sure it is on PATH."
    except (OSError, RuntimeError) as exc:
        return "", f"Error in jq filter: {exc}"


async def run_jq_file_async(json_path: str | os.PathLike, jq_filter: str) -> tuple[str, str]:
    try:
        async with aiofiles.open(json_path, "r", encoding="utf-8") as source:
            json_text = await source.read()
    except OSError as exc:
        raise FileNotFoundError(f"Cannot read JSON file: {exc}") from exc
    return await run_jq_text_async(jq_filter, json_text)


async def run_jq_async(arg1, arg2):
    if _is_file_argument(arg1):
        out, error = await run_jq_file_async(arg1, arg2)
        if error:
            raise ValueError(error)
        return out, error
    return await run_jq_text_async(arg1, arg2)


async def iter_jq_streaming_async(json_file, jq_filter, chunk_size=1000):
    """Yield compact JSON arrays of matching results, one input chunk at a time."""
    wrapper = f"[{jq_filter}]" if _filter_emits_multiple_values(jq_filter) else jq_filter
    chunks = iter_json_array_chunks_async(json_file, chunk_size=chunk_size)
    try:
        async for chunk_json in chunks:
            stdout, stderr = await run_jq_text_async(wrapper, chunk_json)
            if stderr:
                raise RuntimeError(stderr)
            if "\n" in stdout:
                yield merge_stream_results((stdout,))
            elif stdout.startswith("["):
                yield stdout
            elif stdout:
                yield f"[{stdout}]"
    finally:
        await chunks.aclose()


async def run_jq_streaming_async(json_file, jq_filter, chunk_size=1000):
    chunks = iter_jq_streaming_async(json_file, jq_filter, chunk_size=chunk_size)
    results = []
    try:
        async for chunk in chunks:
            _extend_results(results, chunk)
        return dumps(results), ""
    except Exception as exc:
        return "", f"Streaming execution error: {exc}"
    finally:
        await chunks.aclose()
