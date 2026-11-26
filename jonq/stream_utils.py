from __future__ import annotations

import asyncio
from contextlib import closing
from itertools import chain
import json
from pathlib import Path
import re
import shutil
import tempfile

from jonq.json_utils import dumps, loads


_READ_SIZE = 65_536
_CHUNK_CHAR_TARGET = 1_048_576
_JSON_WHITESPACE = " \t\r\n"
_NONSPACE = re.compile(r"[^ \t\r\n]")
_VALUE_MARKER = re.compile(r'["\[\]{},]')
_STRING_MARKER = re.compile(r'["\\]')
_EXPECTED_CLOSER = {"[": "]", "{": "}"}
_ROOT_ARRAY_ERROR = (
    "Streaming mode only works with JSON files containing an array at the root level"
)


def detect_json_structure(json_file):
    with open(json_file, "r", encoding="utf-8") as source:
        char = source.read(1)
        while char and char in _JSON_WHITESPACE:
            char = source.read(1)
        return char == "["


def _iter_root_array_values(source):
    """Frame original JSON values. The stdlib decoder checks their syntax per chunk."""
    opened = False
    closed = False
    after_comma = False
    collecting = False
    in_string = False
    escaped = False
    closers: list[str] = []
    fragments: list[str] = []

    while block := source.read(_READ_SIZE):
        start = 0
        cursor = int(escaped)
        escaped = False
        while cursor < len(block):
            if not collecting:
                first = _NONSPACE.search(block, cursor)
                if first is None:
                    break
                cursor = first.start()
                char = first.group()
                if closed:
                    raise ValueError("Invalid JSON array: extra data after the closing bracket")
                if not opened:
                    if char != "[":
                        raise ValueError(_ROOT_ARRAY_ERROR)
                    opened = True
                    cursor += 1
                    continue
                if char == "]" and not after_comma:
                    closed = True
                    cursor += 1
                    continue
                if char in ",]":
                    raise ValueError("Invalid JSON array: expected a value")
                collecting = True
                start = cursor

            marker = (_STRING_MARKER if in_string else _VALUE_MARKER).search(block, cursor)
            if marker is None:
                break
            cursor = marker.end()
            char = marker.group()
            if in_string:
                if char == "\\":
                    cursor += 1
                    escaped = cursor > len(block)
                else:
                    in_string = False
            elif char == '"':
                in_string = True
            elif char in _EXPECTED_CLOSER:
                closers.append(_EXPECTED_CLOSER[char])
            elif closers:
                if char != "," and char != closers.pop():
                    raise ValueError("Invalid JSON array: mismatched brackets")
            elif char == "}":
                raise ValueError("Invalid JSON array: unexpected closing brace")
            else:
                fragments.append(block[start:marker.start()])
                value = "".join(fragments).rstrip(_JSON_WHITESPACE)
                fragments.clear()
                collecting = False
                after_comma = char == ","
                closed = not after_comma
                yield value

        if collecting:
            fragments.append(block[start:])

    if not opened:
        raise ValueError(_ROOT_ARRAY_ERROR)
    if not closed:
        raise ValueError("Invalid JSON array: unexpected end before the closing bracket")


def _join_validated_chunk(values: list[str]) -> str:
    chunk = "[" + ",".join(values) + "]"
    json.loads(chunk)
    return chunk


def iter_json_array_chunks(json_file, chunk_size=1000):
    with open(json_file, "r", encoding="utf-8", newline="") as source:
        values: list[str] = []
        chars = 0
        for value in _iter_root_array_values(source):
            values.append(value)
            chars += len(value) + 1
            if len(values) >= chunk_size or chars >= _CHUNK_CHAR_TARGET:
                yield _join_validated_chunk(values)
                values.clear()
                chars = 0
        if values:
            yield _join_validated_chunk(values)


async def iter_json_array_chunks_async(json_file, chunk_size=1000):
    with closing(iter_json_array_chunks(json_file, chunk_size)) as chunks:
        while True:
            reading = asyncio.create_task(asyncio.to_thread(next, chunks, None))
            try:
                chunk = await asyncio.shield(reading)
            except asyncio.CancelledError:
                # Close only once the reader has left the generator.
                try:
                    await reading
                finally:
                    raise
            if chunk is None:
                return
            yield chunk


def split_json_array(json_file, chunk_size=1000):
    temp_dir = tempfile.mkdtemp(prefix="jonq_")
    chunk_files = []
    try:
        with closing(iter_json_array_chunks(json_file, chunk_size)) as chunks:
            for index, chunk in enumerate(chain((next(chunks, "[]"),), chunks)):
                path = Path(temp_dir) / f"chunk_{index:06d}"
                path.write_text(chunk, encoding="utf-8")
                chunk_files.append(str(path))
        return temp_dir, chunk_files
    except BaseException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


async def split_json_array_async(json_file, chunk_size=1000):
    return await asyncio.to_thread(split_json_array, json_file, chunk_size)


def _extend_results(results, chunk_result):
    if not chunk_result:
        return
    try:
        value = loads(chunk_result)
    except json.JSONDecodeError:
        try:
            values = [loads(line) for line in chunk_result.split("\n") if line]
        except json.JSONDecodeError:
            results.append(chunk_result)
        else:
            results.extend(values)
    else:
        results.extend(value if isinstance(value, list) else [value])


def merge_stream_results(chunk_results):
    results = []
    for chunk_result in chunk_results:
        _extend_results(results, chunk_result)
    return dumps(results)


def process_json_streaming_inline(json_file, process_func, chunk_size=1000):
    with closing(iter_json_array_chunks(json_file, chunk_size)) as chunks:
        return merge_stream_results(process_func(chunk) for chunk in chunks)


async def process_json_streaming_inline_async(json_file, process_func, chunk_size=1000):
    results = []
    chunks = iter_json_array_chunks_async(json_file, chunk_size)
    try:
        async for chunk in chunks:
            _extend_results(results, await process_func(chunk))
    finally:
        await chunks.aclose()
    return dumps(results)


def process_json_streaming(json_file, process_func, chunk_size=1000):
    temp_dir, chunk_files = split_json_array(json_file, chunk_size)
    try:
        return merge_stream_results(process_func(chunk_file) for chunk_file in chunk_files)
    finally:
        shutil.rmtree(temp_dir)


async def process_json_streaming_async(json_file, process_func, chunk_size=1000):
    temp_dir, chunk_files = await split_json_array_async(json_file, chunk_size)
    try:
        return merge_stream_results(await asyncio.gather(*(process_func(chunk_file) for chunk_file in chunk_files)))
    finally:
        shutil.rmtree(temp_dir)
