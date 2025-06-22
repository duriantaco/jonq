import pytest
import time
import os
import tempfile
import json as stdlib_json
import aiofiles
from jonq.json_utils import dumps, loads
from jonq.stream_utils import process_json_streaming, process_json_streaming_async
from jonq.executor import run_jq, run_jq_streaming, run_jq_async, run_jq_streaming_async

class TestJsonOptimization:
    @pytest.fixture
    def test_data(self):
        """Create test data of various sizes"""
        return {
            "small": [{"id": i, "name": f"Item {i}"} for i in range(10)],
            "medium": [{"id": i, "name": f"Item {i}", "nested": {"values": list(range(20))}} for i in range(100)],
            "large": [{"id": i, "name": f"Item {i}", "nested": {"values": list(range(50))}} for i in range(1000)]
        }
    
    def test_json_correctness(self, test_data):
        for name, data in test_data.items():
            serialized = dumps(data)
            deserialized = loads(serialized)
            
            assert deserialized == data, f"Data corruption in {name} dataset"
            
            stdlib_serialized = stdlib_json.dumps(data)
            stdlib_deserialized = stdlib_json.loads(stdlib_serialized)
            
            assert deserialized == stdlib_deserialized, f"Output differs from stdlib in {name} dataset"
    
    def test_json_performance(self, test_data):
        data = test_data["large"]
        start = time.time()
        for _ in range(50):
            dumps(data)
        custom_dumps_time = time.time() - start
        
        start = time.time()
        for _ in range(50):
            stdlib_json.dumps(data)
        stdlib_dumps_time = time.time() - start
        
        serialized = dumps(data)
        stdlib_serialized = stdlib_json.dumps(data)
        
        start = time.time()
        for _ in range(50):
            loads(serialized)
        custom_loads_time = time.time() - start
        
        start = time.time()
        for _ in range(50):
            stdlib_json.loads(stdlib_serialized)
        stdlib_loads_time = time.time() - start
        
        print(f"\nJSON Performance Results:")
        print(f"  Serialization   - Custom: {custom_dumps_time:.4f}s, Stdlib: {stdlib_dumps_time:.4f}s")
        print(f"  Deserialization - Custom: {custom_loads_time:.4f}s, Stdlib: {stdlib_loads_time:.4f}s")
        
        using_orjson = custom_dumps_time < stdlib_dumps_time * 0.7
        print(f"  Using orjson: {'Yes' if using_orjson else 'No (fallback to stdlib)'}")
    
    def test_stream_utils_integration(self, test_data):
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
            temp_file.write(dumps(test_data["medium"]))
            temp_path = temp_file.name
            
        try:
            def process_chunk(chunk_file):
                with open(chunk_file, 'r') as f:
                    data = loads(f.read())
                    for item in data:
                        item["id"] *= 2
                    return dumps(data)
            
            result = process_json_streaming(temp_path, process_chunk, chunk_size=20)
            
            processed_data = loads(result)
            assert len(processed_data) == len(test_data["medium"])
            assert processed_data[0]["id"] == test_data["medium"][0]["id"] * 2
            
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_stream_utils_integration_async(self, test_data):
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
            temp_file.write(dumps(test_data["medium"]))
            temp_path = temp_file.name
            
        try:
            async def process_chunk_async(chunk_file):
                async with aiofiles.open(chunk_file, 'r') as f:
                    data = loads(await f.read())
                    for item in data:
                        item["id"] *= 2
                    return dumps(data)
            
            result = await process_json_streaming_async(temp_path, process_chunk_async, chunk_size=20)
            
            processed_data = loads(result)
            assert len(processed_data) == len(test_data["medium"])
            assert processed_data[0]["id"] == test_data["medium"][0]["id"] * 2
            
        finally:
            os.unlink(temp_path)
    
    def test_unicode_handling(self):
        data = {
            "text": "Hello, 世界! 🌍 привет",
            "special_chars": "\n\t\b\f\r\"\\/"
        }
        
        serialized = dumps(data)
        deserialized = loads(serialized)
        
        assert deserialized == data