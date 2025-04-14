import json
import subprocess
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

def detect_json_structure(json_file):
    """
    Detect if the JSON file contains an array at the root level.
    """
    with open(json_file, 'r') as f:
        char = ' '
        while char.isspace() and char:
            char = f.read(1)
        return char == '['

def split_json_array(json_file, chunk_size=1000):
    """
    Split a JSON array file into chunks for streaming processing.
    """
    temp_dir = tempfile.mkdtemp(prefix="jonq_")
    chunk_base = os.path.join(temp_dir, "chunk_")
    
    try:
        cmd = f"jq -c '.[]' {json_file} | split -l {chunk_size} - {chunk_base}"
        subprocess.run(cmd, shell=True, check=True)
        
        chunk_files = []
        for filename in sorted(os.listdir(temp_dir)):
            if filename.startswith("chunk_"):
                chunk_path = os.path.join(temp_dir, filename)
                with open(chunk_path, 'r') as f:
                    content = f.read()
                
                with open(chunk_path, 'w') as f:
                    f.write('[' + content.replace('\n', ',').rstrip(',') + ']')
                
                chunk_files.append(chunk_path)
        
        return temp_dir, chunk_files
    
    except subprocess.CalledProcessError as e:
        import shutil
        shutil.rmtree(temp_dir)
        raise RuntimeError(f"Error splitting JSON into chunks: {str(e)}")

def process_json_streaming(json_file, process_func, chunk_size=1000):
    """
    Process a large JSON file in streaming mode.
    """
    if not detect_json_structure(json_file):
        raise ValueError("Streaming mode only works with JSON files containing an array at the root level")
    
    try:
        temp_dir, chunk_files = split_json_array(json_file, chunk_size)
        
        all_results = []
        for chunk_file in chunk_files:
            logger.info(f"Processing chunk: {chunk_file}")
            chunk_result = process_func(chunk_file)
            
            try:
                result_data = json.loads(chunk_result)
                if isinstance(result_data, list):
                    all_results.extend(result_data)
                else:
                    all_results.append(result_data)
            except json.JSONDecodeError:
                all_results.append(chunk_result)
        
        import shutil
        shutil.rmtree(temp_dir)
        
        if all(isinstance(r, (dict, list)) for r in all_results):
            return json.dumps(all_results)
        else:
            return '\n'.join(str(r) for r in all_results)
            
    except Exception as e:
        logger.error(f"Error in streaming process: {str(e)}")
        raise