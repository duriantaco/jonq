import json
import logging
import os
import inspect

from jonq.jq_worker_cli import get_worker, get_worker_async
from jonq.stream_utils import process_json_streaming, process_json_streaming_async
import aiofiles
import asyncio

logger = logging.getLogger(__name__)

def _run_jq_raw(jq_filter, json_text):
    worker = None
    try:
        worker = get_worker(jq_filter)
        out = worker.query(json.loads(json_text))
        return out, ""
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON: {exc}"
    except Exception as exc:
        return "", f"Error in jq filter: {exc}"
    finally:
        try:
            if worker:
                closer = getattr(worker, "aclose", None) or getattr(worker, "close", None)
                if closer:
                    if inspect.iscoroutinefunction(closer):
                        try:
                            asyncio.run(closer())
                        except RuntimeError:
                            import threading
                            def _runner():
                                asyncio.run(closer())
                            t = threading.Thread(target=_runner, daemon=True)
                            t.start()
                            t.join()
                    else:
                        closer()
        except Exception:
            pass

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
            raise RuntimeError(f"Error in jq filter: {err}")
        return out, err

    return _run_jq_raw(arg1, arg2)

def run_jq_streaming(json_file, jq_filter, chunk_size=1000):
    emits_objects = jq_filter.startswith(".[]") or "| .[" in jq_filter
    wrapper = f"[{jq_filter}]" if emits_objects else jq_filter

    def _process_chunk(chunk_path):
        with open(chunk_path, "r", encoding="utf-8") as fp:
            chunk_json = fp.read()
        stdout, stderr = run_jq(wrapper, chunk_json)
        if stderr:
            raise RuntimeError(stderr)
        return stdout

    try:
        merged_json = process_json_streaming(
            json_file,
            _process_chunk,
            chunk_size=chunk_size
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
    worker = None
    try:
        worker = await get_worker_async(jq_filter)
        out = await worker.query(json.loads(json_text))
        return out, ""
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON: {exc}"
    except Exception as exc:
        return "", f"Error in jq filter: {exc}"
    finally:
        try:
            if worker:
                closer = getattr(worker, "aclose", None) or getattr(worker, "close", None)
                if closer:
                    if inspect.iscoroutinefunction(closer):
                        await closer()
                    else:
                        closer()
        except Exception:
            pass

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
            raise RuntimeError(f"Error in jq filter: {err}")
        return out, err

    return await _run_jq_raw_async(arg1, arg2)

async def run_jq_streaming_async(json_file, jq_filter, chunk_size=1000):
    emits_objects = jq_filter.startswith(".[]") or "| .[" in jq_filter
    wrapper = f"[{jq_filter}]" if emits_objects else jq_filter

    async def _process_chunk_async(chunk_path):
        async with aiofiles.open(chunk_path, "r", encoding="utf-8") as fp:
            chunk_json = await fp.read()
        stdout, stderr = await run_jq_async(wrapper, chunk_json)
        if stderr:
            raise RuntimeError(stderr)
        return stdout

    try:
        merged_json = await process_json_streaming_async(
            json_file,
            _process_chunk_async,
            chunk_size=chunk_size
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