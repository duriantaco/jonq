import subprocess

def run_jq(json_file, jq_filter):
    """
    Execute a jq filter on a JSON file.

    This function runs the jq command-line tool to process JSON data with a given filter.

    Args:
        json_file (str): Path to the JSON file to process
        jq_filter (str): jq filter expression to apply to the JSON data

    Returns:
        tuple: A tuple containing (stdout, stderr) where:
            - stdout (str): The filtered JSON output
            - stderr (str): Any error messages from jq
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