import json
import subprocess
import tempfile
import os
import logging
import shutil
from jonq.json_utils import dumps, loads 
import shutil
import asyncio
import aiofiles

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

def split_json_array(json_file: str, chunk_size: int = 1000) -> tuple[str, list[str]]:

    temp_dir = tempfile.mkdtemp(prefix="jonq_")
    chunk_files: list[str] = []

    try:
        proc = subprocess.Popen(
            ['jq', '-c', '.[]', json_file],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        current_chunk_idx = 0
        current_line_count = 0
        current_path = os.path.join(temp_dir, f"chunk_{current_chunk_idx:06d}")
        current_handle = open(current_path, 'w', encoding='utf-8')
        current_handle.write('[')

        for line in proc.stdout:
            if current_line_count:
                current_handle.write(',')
            current_handle.write(line.strip())
            current_line_count += 1

            if current_line_count >= chunk_size:
                current_handle.write(']')
                current_handle.close()
                chunk_files.append(current_path)

                # reset counters 
                current_chunk_idx += 1
                current_line_count = 0
                current_path = os.path.join(temp_dir, f"chunk_{current_chunk_idx:06d}")
                current_handle = open(current_path, 'w', encoding='utf-8')
                current_handle.write('[')

        current_handle.write(']')
        current_handle.close()
        chunk_files.append(current_path)

        jq_err = proc.stderr.read()
        if proc.wait() != 0:
            raise RuntimeError(f"jq failed: {jq_err.strip()}")

        return temp_dir, chunk_files

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

def process_json_streaming(json_file, process_func, chunk_size=1000):
    if not detect_json_structure(json_file):
        raise ValueError("Streaming mode only works with JSON files containing an array at the root level")
    
    try:
        temp_dir, chunk_files = split_json_array(json_file, chunk_size)
        
        all_results = []
        for chunk_file in chunk_files:
            logger.info(f"Processing chunk: {chunk_file}")
            chunk_result = process_func(chunk_file)
            
            try:
                result_data = loads(chunk_result)
                if isinstance(result_data, list):
                    all_results.extend(result_data)
                else:
                    all_results.append(result_data)
            except json.JSONDecodeError:
                all_results.append(chunk_result)
        
        shutil.rmtree(temp_dir)
        
        if all(isinstance(r, (dict, list)) for r in all_results):
            return dumps(all_results)
        else:
            return '\n'.join(str(r) for r in all_results)
            
    except Exception as e:
        logger.error(f"Error in streaming process: {str(e)}")
        raise

#### adding async version for streaming processing ####

async def split_json_array_async(json_file: str, chunk_size: int = 1000) -> tuple[str, list[str]]:
    temp_dir = tempfile.mkdtemp(prefix="jonq_")
    chunk_files: list[str] = []

    try:
        proc = await asyncio.create_subprocess_exec(
            'jq', '-c', '.[]', json_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True
        )

        current_chunk_idx = 0
        current_line_count = 0
        current_path = os.path.join(temp_dir, f"chunk_{current_chunk_idx:06d}")
        current_handle = await aiofiles.open(current_path, 'w', encoding='utf-8')
        await current_handle.write('[')

        async for line in proc.stdout:
            if current_line_count:
                await current_handle.write(',')
            await current_handle.write(line.strip())
            current_line_count += 1

            if current_line_count >= chunk_size:
                await current_handle.write(']')
                await current_handle.close()
                chunk_files.append(current_path)

                current_chunk_idx += 1
                current_line_count = 0
                current_path = os.path.join(temp_dir, f"chunk_{current_chunk_idx:06d}")
                current_handle = await aiofiles.open(current_path, 'w', encoding='utf-8')
                await current_handle.write('[')

        await current_handle.write(']')
        await current_handle.close()
        chunk_files.append(current_path)

        stderr_data = await proc.stderr.read()
        await proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"jq failed: {stderr_data.strip()}")

        return temp_dir, chunk_files

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

async def process_json_streaming_async(json_file, process_func, chunk_size=1000):
    if not detect_json_structure(json_file):
        raise ValueError("Streaming mode only works with JSON files containing an array at the root level")
    
    try:
        temp_dir, chunk_files = await split_json_array_async(json_file, chunk_size)
        
        # Process chunks concurrently instead of sequentially
        tasks = []
        for chunk_file in chunk_files:
            logger.info(f"Processing chunk: {chunk_file}")
            task = process_func(chunk_file)
            tasks.append(task)
        
        chunk_results = await asyncio.gather(*tasks)
        
        all_results = []
        for chunk_result in chunk_results:
            try:
                result_data = loads(chunk_result)
                if isinstance(result_data, list):
                    all_results.extend(result_data)
                else:
                    all_results.append(result_data)
            except json.JSONDecodeError:
                all_results.append(chunk_result)
        
        shutil.rmtree(temp_dir)
        
        if all(isinstance(r, (dict, list)) for r in all_results):
            return dumps(all_results)
        else:
            return '\n'.join(str(r) for r in all_results)
            
    except Exception as e:
        logger.error(f"Error in streaming process: {str(e)}")
        raise