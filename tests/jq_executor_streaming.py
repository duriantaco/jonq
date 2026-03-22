import os
import json
import tempfile
from jonq.executor import run_jq, run_jq_streaming
from jonq.executor import run_jq_async, run_jq_streaming_async
from jonq.jq_worker_cli import get_worker_async, _cleanup_async
import pytest
import asyncio

class TestExecutorStreaming:
    def setup_method(self):
        self.large_json = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
        
        array_data = [{"id": i, "name": f"Item {i}", "active": i % 2 == 0} for i in range(1, 501)]
        json.dump(array_data, self.large_json)
        self.large_json.close()
    
    def teardown_method(self):
        os.unlink(self.large_json.name)
    
    def test_run_jq_streaming(self):
        jq_filter = '.[] | select(.active == true)'
        stdout, stderr = run_jq_streaming(self.large_json.name, jq_filter, chunk_size=100)
        
        assert stderr == ""
        
        output = json.loads(stdout)
        
        assert len(output) == 250
        
        assert output[0]["id"] == 2
        assert output[-1]["id"] == 500
    
    def test_compare_streaming_vs_regular(self):
        jq_filter = '[.[] | select(.id > 250)]'
        
        regular_stdout, _ = run_jq(self.large_json.name, jq_filter)
        streaming_stdout, _ = run_jq_streaming(self.large_json.name, jq_filter)
        
        regular_data = json.loads(regular_stdout)
        streaming_data = json.loads(streaming_stdout)
        
        assert len(regular_data) == len(streaming_data)
        
        regular_ids = sorted([item["id"] for item in regular_data])
        streaming_ids = sorted([item["id"] for item in streaming_data])
        assert regular_ids == streaming_ids
    
    def test_run_jq_streaming_error(self):
        jq_filter = '.[] | invalid_function'
        stdout, stderr = run_jq_streaming(self.large_json.name, jq_filter)
        
        assert stdout == ""
        assert "Error" in stderr

    def test_compare_individual_objects_handling(self):
        filter_individual = '.[] | select(.id > 490)'
        
        compact_filter = filter_individual + " | tostring" 
        regular_stdout, _ = run_jq(self.large_json.name, compact_filter)
        
        array_filter = '[' + filter_individual + ']'
        array_stdout, _ = run_jq(self.large_json.name, array_filter)
        regular_objects = json.loads(array_stdout)
                
        streaming_stdout, _ = run_jq_streaming(self.large_json.name, filter_individual)
        streaming_objects = json.loads(streaming_stdout)
        
        assert len(regular_objects) == len(streaming_objects)
        
        regular_ids = sorted([item["id"] for item in regular_objects])
        streaming_ids = sorted([item["id"] for item in streaming_objects])
        assert regular_ids == streaming_ids

class TestExecutorStreamingAsync:
    def setup_method(self):
        self.large_json = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
        
        array_data = [{"id": i, "name": f"Item {i}", "active": i % 2 == 0} for i in range(1, 501)]
        json.dump(array_data, self.large_json)
        self.large_json.close()
    
    def teardown_method(self):
        os.unlink(self.large_json.name)
    
    @pytest.mark.asyncio
    async def test_run_jq_streaming_async(self):
        jq_filter = '.[] | select(.active == true)'
        stdout, stderr = await run_jq_streaming_async(self.large_json.name, jq_filter, chunk_size=100)
        
        assert stderr == ""
        
        output = json.loads(stdout)
        
        assert len(output) == 250
        
        assert output[0]["id"] == 2
        assert output[-1]["id"] == 500
    
    @pytest.mark.asyncio
    async def test_compare_streaming_vs_regular_async(self):
        jq_filter = '[.[] | select(.id > 250)]'
        
        regular_stdout, _ = await run_jq_async(self.large_json.name, jq_filter)
        streaming_stdout, _ = await run_jq_streaming_async(self.large_json.name, jq_filter)
        
        regular_data = json.loads(regular_stdout)
        streaming_data = json.loads(streaming_stdout)
        
        assert len(regular_data) == len(streaming_data)
        
        regular_ids = sorted([item["id"] for item in regular_data])
        streaming_ids = sorted([item["id"] for item in streaming_data])
        assert regular_ids == streaming_ids
    
    @pytest.mark.asyncio
    async def test_run_jq_streaming_error_async(self):
        jq_filter = '.[] | invalid_function'
        stdout, stderr = await run_jq_streaming_async(self.large_json.name, jq_filter)
        
        assert stdout == ""
        assert "Error" in stderr

    @pytest.mark.asyncio
    async def test_concurrent_processing(self):
        tasks = [
            run_jq_async(self.large_json.name, '[.[] | select(.id > 400)]'),
            run_jq_async(self.large_json.name, '[.[] | select(.id < 100)]'),
            run_jq_async(self.large_json.name, '[.[] | select(.active == true)]')
        ]
        
        results = await asyncio.gather(*tasks)
        
        for stdout, stderr in results:
            assert stderr == ""
            data = json.loads(stdout)
            assert len(data) > 0

    @pytest.mark.asyncio
    async def test_run_jq_async_runtime_error(self):
        single_json = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
        try:
            json.dump({"name": "Alice", "age": 30}, single_json)
            single_json.close()

            with pytest.raises(ValueError) as excinfo:
                await run_jq_async(single_json.name, '.name[]')

            assert "Error in jq filter" in str(excinfo.value)
            assert "Cannot iterate over string" in str(excinfo.value)
        finally:
            os.unlink(single_json.name)

    @pytest.mark.asyncio
    async def test_run_jq_async_reuses_cached_worker(self):
        await _cleanup_async()

        stdout, stderr = await run_jq_async(
            self.large_json.name, '[.[] | select(.id > 498)]'
        )
        assert stderr == ""
        assert len(json.loads(stdout)) == 2

        worker = await get_worker_async('[.[] | select(.id > 498)]')
        first_pid = worker.proc.pid
        assert worker.proc.returncode is None

        stdout, stderr = await run_jq_async(
            self.large_json.name, '[.[] | select(.id > 498)]'
        )
        assert stderr == ""
        assert len(json.loads(stdout)) == 2

        worker = await get_worker_async('[.[] | select(.id > 498)]')
        assert worker.proc.pid == first_pid
        assert worker.proc.returncode is None

        await _cleanup_async()
