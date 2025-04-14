import subprocess
import json
import logging

logger = logging.getLogger(__name__)

def run_jq(json_file, jq_filter):
    """
    Run jq filter on a JSON file and return stdout/stderr.
    """
    cmd = ['jq', jq_filter, json_file]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        error_msg = result.stderr.strip()
        if "parse error" in error_msg:
            if "unexpected end of input" in error_msg:
                raise ValueError(f"Malformed JSON in '{json_file}': File appears to be truncated or has unclosed brackets/braces.")
            elif "expected value" in error_msg:
                raise ValueError(f"Malformed JSON in '{json_file}': Expected a value but found something else. Check for missing commas or quotes.")
            elif "unexpected" in error_msg:
                raise ValueError(f"Malformed JSON in '{json_file}': Unexpected character found. Check for missing quotes or syntax errors.")
            else:
                raise ValueError(f"Invalid JSON in '{json_file}': {error_msg}. Please verify your JSON structure.")
        else:
            raise ValueError(f"Error in jq filter '{jq_filter}': {error_msg}")
    return result.stdout, result.stderr

def run_jq_streaming(json_file, jq_filter, chunk_size=1000):
    """
    Run jq filter on a JSON file in streaming mode.
    """
    from jonq.stream_utils import process_json_streaming
    
    produces_individual_objects = jq_filter.startswith('.[]') or '| .[' in jq_filter
    
    if produces_individual_objects:
        wrapping_filter = f"[{jq_filter}]"
    else:
        wrapping_filter = jq_filter
    
    def process_chunk(chunk_file):
        try:
            stdout, stderr = run_jq(chunk_file, wrapping_filter)
            if stderr:
                raise ValueError(f"Error processing chunk: {stderr}")
            return stdout
        except Exception as e:
            logger.error(f"Error processing chunk: {str(e)}")
            raise
    
    try:
        results_json = process_json_streaming(json_file, process_chunk, chunk_size)
        
        if produces_individual_objects:
            try:
                results_array = json.loads(results_json)
                
                if not isinstance(results_array, list):
                    results_array = [results_array]
                
                return json.dumps(results_array), ""
            except json.JSONDecodeError as e:
                return "", f"Error parsing results: {str(e)}"
        else:
            return results_json, ""
            
    except ValueError as e:
        return "", str(e)
    except Exception as e:
        logger.error(f"Streaming execution error: {str(e)}")
        return "", f"Streaming execution error: {str(e)}"