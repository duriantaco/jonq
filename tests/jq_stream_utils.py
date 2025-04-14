import pytest
import os
import json
import tempfile
from jonq.stream_utils import detect_json_structure, split_json_array, process_json_streaming

class TestStreamUtils:
    def setup_method(self):
        self.array_json = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
        self.object_json = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
        
        array_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]
        json.dump(array_data, self.array_json)
        self.array_json.close()
        
        object_data = {"id": 1, "name": "Test Object", "items": list(range(1, 10))}
        json.dump(object_data, self.object_json)
        self.object_json.close()
    
    def teardown_method(self):
        os.unlink(self.array_json.name)
        os.unlink(self.object_json.name)
    
    def test_detect_json_structure(self):
        assert detect_json_structure(self.array_json.name) == True
        
        assert detect_json_structure(self.object_json.name) == False
    
    def test_split_json_array(self):
        temp_dir, chunk_files = split_json_array(self.array_json.name, chunk_size=20)
        
        try:
            assert len(chunk_files) == 5
            
            with open(chunk_files[0], 'r') as f:
                chunk_data = json.load(f)
                assert len(chunk_data) == 20
                assert chunk_data[0]["id"] == 1
                assert chunk_data[19]["id"] == 20
            
            with open(chunk_files[-1], 'r') as f:
                chunk_data = json.load(f)
                assert len(chunk_data) == 20
                assert chunk_data[0]["id"] == 81
                assert chunk_data[-1]["id"] == 100
                
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_process_json_streaming(self):
        def process_chunk(chunk_file):
            with open(chunk_file, 'r') as f:
                data = json.load(f)
                for item in data:
                    item["id"] *= 2
                return json.dumps(data)
        
        result = process_json_streaming(self.array_json.name, process_chunk, chunk_size=25)
        
        processed_data = json.loads(result)
        
        assert len(processed_data) == 100
        assert processed_data[0]["id"] == 2
        assert processed_data[50]["id"] == 102
        assert processed_data[-1]["id"] == 200
    
    def test_process_json_streaming_not_array(self):
        def process_chunk(chunk_file):
            return "test"
        
        with pytest.raises(ValueError) as excinfo:
            process_json_streaming(self.object_json.name, process_chunk)
        
        assert "Streaming mode only works with JSON files" in str(excinfo.value)
