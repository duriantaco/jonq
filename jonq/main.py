import sys
import os
from jonq.query_parser import tokenize, parse_query
from jonq.jq_filter import generate_jq_filter
from jonq.executor import run_jq, run_jq_streaming
from jonq.csv_utils import json_to_csv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """
    jonq Command Line Interface.

    This is the entry point for jonq cli.
    It parses queries, translates them to jq filters, and executes them.
    """
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print("Usage: jonq <path/json_file> <query> [options]")
        print("\nOptions:")
        print("  --format, -f csv|json   Output format (default: json)")
        print("  --stream, -s            Process large files in streaming mode (for arrays)")
        print("  -h, --help              Show this help message")
        sys.exit(0)
        
    if len(sys.argv) < 3:
        print("Usage: jonq <path/json_file> <query> [options]")
        print("Try 'jonq --help' for more information.")
        sys.exit(1)
        
    json_file = sys.argv[1]
    query = sys.argv[2]
    
    output_format = "json"
    use_streaming = False
    
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] in ["--format", "-f"] and i + 1 < len(sys.argv):
            if sys.argv[i + 1].lower() == "csv":
                output_format = "csv"
            i += 2
        elif sys.argv[i] in ["--stream", "-s"]:
            use_streaming = True
            i += 1
        else:
            print(f"Unknown option: {sys.argv[i]}")
            print("Try 'jonq --help' for more information.")
            sys.exit(1)
            
    try:
        if not os.path.exists(json_file):
            raise FileNotFoundError(f"JSON file '{json_file}' not found. Please check the file path.")
        if not os.path.isfile(json_file):
            raise FileNotFoundError(f"JSON file '{json_file}' not found.")
        if not os.access(json_file, os.R_OK):
            raise PermissionError(f"Cannot read JSON file '{json_file}'.")
        
        file_size = os.path.getsize(json_file)
        if file_size == 0:
            raise ValueError(f"JSON file '{json_file}' is empty. Please provide a non-empty JSON file.")
        
        tokens = tokenize(query)
        fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
        jq_filter = generate_jq_filter(fields, condition, group_by, order_by, sort_direction, limit)
        
        if use_streaming:
            logger.info("Using streaming mode for processing")
            stdout, stderr = run_jq_streaming(json_file, jq_filter)
        else:
            stdout, stderr = run_jq(json_file, jq_filter)
        
        if stdout:
            if output_format == "csv":
                csv_output = json_to_csv(stdout)
                print(csv_output.strip())
            else:
                print(stdout.strip())
                
        if stderr:
            logger.error(f"JQ error: {stderr}")
            
    except ValueError as e:
        print(f"Query Error: {e}. Please check your query syntax.")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"File Error: {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"Permission Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Execution Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()