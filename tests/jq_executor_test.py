import pytest
import os
import json
import tempfile
from jonq.executor import run_jq

def test_run_jq_success():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp:
        json.dump({"name": "Alice", "age": 30}, temp)
        temp_path = temp.name
    
    try:
        stdout, stderr = run_jq(temp_path, '.name')
        assert '"Alice"' in stdout
        assert stderr == ''
        
        stdout, stderr = run_jq(temp_path, '.age')
        assert '30' in stdout
        assert stderr == ''
    finally:
        os.unlink(temp_path)

def test_run_jq_malformed_json():
    with open(tempfile.mktemp(suffix='.json'), 'w') as temp:
        temp.write('{"name": "Alice", "age": 30') 
        temp_path = temp.name
    
    try:
        with pytest.raises(ValueError) as excinfo:
            run_jq(temp_path, '.name')
        assert "Invalid JSON" in str(excinfo.value)
    finally:
        os.unlink(temp_path)

def test_run_jq_invalid_filter():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp:
        json.dump({"name": "Alice", "age": 30}, temp)
        temp_path = temp.name
    
    try:
        with pytest.raises(ValueError) as excinfo:
            run_jq(temp_path, '.name[]')
        assert "Error in jq filter" in str(excinfo.value)
    finally:
        os.unlink(temp_path)