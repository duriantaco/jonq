import sys
import os
from jonq.query_parser import tokenize, parse_query
from jonq.jq_filter import generate_jq_filter
from jonq.executor import run_jq
import logging

logging.basicConfig(level=logging.INFO)

def main():
    """
    jonq Command Line Interface.

    This is the entry point for jonq cli.
    It parses queries, translates them to jq filters, and executes them.
    """
    if len(sys.argv) != 3:
        print("Usage: jonq <path/json_file> <query> -> query in double quotation marks")
        sys.exit(1)
    json_file = sys.argv[1]
    query = sys.argv[2]
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
        stdout, stderr = run_jq(json_file, jq_filter)
        if stdout:
            print(stdout.strip())
        if stderr:
            logging.error(f"JQ error: {stderr}")
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