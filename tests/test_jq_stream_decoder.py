import asyncio
from contextlib import contextmanager
import json

import pytest

from jonq.executor import iter_jq_streaming_async, run_jq_streaming, run_jq_streaming_async
from jonq.stream_utils import iter_json_array_chunks, iter_json_array_chunks_async


async def collect_chunks(path, chunk_size):
    return [
        chunk
        async for chunk in iter_json_array_chunks_async(path, chunk_size=chunk_size)
    ]


def test_decoder_preserves_rows_at_block_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr("jonq.stream_utils._READ_SIZE", 5, raising=False)
    values = [
        "escaping \\\" and unicode 雪🦉",
        [1, {"embedded": '[,{}]"'}],
        {},
        None,
        False,
        0.001,
        123456789123456789123456789,
    ]
    source = tmp_path / "rows.json"
    source.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")

    expected = [values[index:index + 2] for index in range(0, len(values), 2)]
    sync_chunks = list(iter_json_array_chunks(source, chunk_size=2))
    async_chunks = asyncio.run(collect_chunks(source, chunk_size=2))
    assert [json.loads(chunk) for chunk in sync_chunks] == expected
    assert async_chunks == sync_chunks


@pytest.mark.parametrize("data", ["[1][2]", "[1] null", "[1,]", "[1, 2", "[1 2]", '[{"a":[1}}]', "[,1]"])
def test_decoder_rejects_incomplete_or_multiple_documents(tmp_path, data):
    source = tmp_path / "bad.json"
    source.write_text(data, encoding="utf-8")

    with pytest.raises(ValueError):
        list(iter_json_array_chunks(source, chunk_size=1))
    with pytest.raises(ValueError):
        asyncio.run(collect_chunks(source, chunk_size=1))


def test_large_zero_match_query_reads_only_bounded_blocks(tmp_path, monkeypatch):
    source = tmp_path / "rows.json"
    row = json.dumps({"active": False, "payload": "x" * 4000})
    with source.open("w", encoding="utf-8") as output:
        output.write("[")
        for index in range(1024):
            output.write("," if index else "")
            output.write(row)
        output.write("]")

    read_sizes = []

    class BoundedReader:
        def __init__(self, stream):
            self.stream = stream

        def read(self, size=-1):
            assert 0 < size <= 65536
            block = self.stream.read(size)
            read_sizes.append(len(block))
            return block

    @contextmanager
    def tracked_open(*arguments, **keywords):
        with open(*arguments, **keywords) as stream:
            yield BoundedReader(stream)

    monkeypatch.setattr("jonq.stream_utils.open", tracked_open, raising=False)
    chunks = iter_json_array_chunks(source, chunk_size=1)
    try:
        assert json.loads(next(chunks)) == [json.loads(row)]
        assert sum(read_sizes) < source.stat().st_size
    finally:
        chunks.close()
    chunks = iter_json_array_chunks(source)
    try:
        first_chunk = next(chunks)
        assert len(first_chunk) <= 1_048_576 + len(row) + 2
        assert sum(read_sizes) < source.stat().st_size
    finally:
        chunks.close()
    assert run_jq_streaming(source, "[.[] | select(.active == true)]") == ("[]", "")
    assert len(read_sizes) > 2


def test_executor_yields_array_chunks_and_discards_incomplete_batch_output(tmp_path):
    source = tmp_path / "rows.json"
    source.write_text("[1,2,3] []", encoding="utf-8")
    jq_filter = ".[]"

    async def examine_streaming_output():
        chunks = iter_jq_streaming_async(source, jq_filter, chunk_size=1)
        try:
            assert json.loads(await chunks.__anext__()) == [1]
            assert json.loads(await chunks.__anext__()) == [2]
            assert json.loads(await chunks.__anext__()) == [3]
            with pytest.raises(ValueError, match="extra data"):
                await chunks.__anext__()
        finally:
            await chunks.aclose()

    asyncio.run(examine_streaming_output())
    for stdout, stderr in (
        run_jq_streaming(source, jq_filter, chunk_size=1),
        asyncio.run(run_jq_streaming_async(source, jq_filter, chunk_size=1)),
    ):
        assert stdout == ""
        assert "extra data" in stderr
