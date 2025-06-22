#!/usr/bin/env python3
import sys
import os
import logging
from jonq.query_parser import tokenize_query, parse_query
from jonq.jq_filter import generate_jq_filter
from jonq.executor import run_jq_async, run_jq_streaming_async
from jonq.csv_utils import json_to_csv
from jonq.error_handler import (
    ErrorAnalyzer, validate_query_against_schema, 
    handle_error_with_context, QuerySyntaxError
)
import asyncio

logger = logging.getLogger(__name__)

async def main():

    logging.basicConfig(
        format='%(levelname)s:%(name)s:%(message)s',
        level=logging.INFO
    )

    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print_help()
        sys.exit(0)
        
    if len(sys.argv) < 3:
        print("Usage: jonq <path/json_file> <query> [options]")
        print("Try 'jonq --help' for more information.")
        sys.exit(1)
        
    json_file = sys.argv[1]
    query = sys.argv[2]
    options = parse_options(sys.argv[3:])

    try:
        validate_input_file(json_file)

        validation_error = validate_query_against_schema(json_file, query)
        if validation_error:
            raise QuerySyntaxError(
                validation_error,
                suggestion="Use 'jonq file.json \"select *\"' to see all available fields"
            )
        
        tokens = tokenize_query(query)
        fields, condition, group_by, having, order_by, sort_direction, limit, from_path = parse_query(tokens)
        jq_filter = generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path)
        
        if os.environ.get('JONQ_DEBUG'):
            logger.info(f"Query: {query}")
            logger.info(f"Generated jq filter: {jq_filter}")
        
        if options['streaming']:
            logger.info("Using streaming mode for processing")
            stdout, stderr = await run_jq_streaming_async(json_file, jq_filter)
        else:
            stdout, stderr = await run_jq_async(json_file, jq_filter)

        if stderr:
            analyzer = ErrorAnalyzer(json_file, query, jq_filter)
            jonq_error = analyzer.analyze_jq_error(stderr)
            raise jonq_error
        
        if stdout:
            if options['format'] == "csv":
                csv_output = json_to_csv(stdout, use_fast=options.get('use_fast', False))
                print(csv_output.strip())
            else:
                print(stdout.strip())
                
    except Exception as e:
        handle_error_with_context(e, json_file, query, jq_filter if 'jq_filter' in locals() else None)
        sys.exit(1)
        
        if stderr:
            if "Cannot iterate over null" in stderr:
                raise RuntimeError(f"Cannot iterate over null values in your JSON. Check field paths in query: {query}")
            elif "is not defined" in stderr and any(x in stderr for x in ["avg/1", "max/1", "min/1", "sum/1"]):
                raise RuntimeError(f"Error in aggregation function. Make sure your field paths exist in the JSON.")
            else:
                raise RuntimeError(f"Error in jq filter: {stderr}")
        
        if stdout:
            logger.info(f"Raw output type: {type(stdout)}, length: {len(stdout)}")
            if options.get('format') == "csv":
                try:
                    csv_output = json_to_csv(stdout, use_fast=options.get('use_fast', False))
                    logger.info(f"CSV output type: {type(csv_output)}, length: {len(csv_output)}")
                    print(csv_output.strip())
                except Exception as e:
                    logger.error(f"Error converting to CSV: {e}")
                    print(stdout.strip())
            else:
                print(stdout.strip())
                
    except Exception as e:
        handle_error(e)

def print_help():
    print("jonq - SQL-like query tool for JSON data")
    print("\nUsage: jonq <path/json_file> <query> [options]")
    print("\nOptions:")
    print("  --format, -f csv|json   Output format (default: json)")
    print("  --stream, -s            Process large files in streaming mode (for arrays)")
    print("  --fast, -F              Use jonq_fast Rust implementation when avail (faster JSON flattening)")
    print("  -h, --help              Show this help message")
    print("\nExamples:")
    print("  jonq data.json \"select * from []\"")
    print("  jonq data.json \"select name, age from [] if age > 30\"")

def parse_options(args):
    options = {'format': 'json', 'streaming': False, 'use_fast': False}
    i = 0
    while i < len(args):
        if args[i] in ["--format", "-f"] and i + 1 < len(args):
            if args[i + 1].lower() == "csv":
                options['format'] = "csv"
            i += 2
        elif args[i] in ["--stream", "-s"]:
            options['streaming'] = True
            i += 1
        elif args[i] in ["--fast", "-F"]:
            options['use_fast'] = True
            i += 1
        else:
            print(f"Unknown option: {args[i]}")
            sys.exit(1)
    return options

def validate_input_file(json_file):
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"JSON file '{json_file}' not found.")
    if not os.path.isfile(json_file):
        raise FileNotFoundError(f"'{json_file}' is not a file.")
    if not os.access(json_file, os.R_OK):
        raise PermissionError(f"Cannot read JSON file '{json_file}'.")
    if os.path.getsize(json_file) == 0:
        raise ValueError(f"JSON file '{json_file}' is empty.")

def handle_error(error):
    if isinstance(error, ValueError):
        print(f"Query Error: {error}")
    elif isinstance(error, FileNotFoundError):
        print(f"File Error: {error}")
    elif isinstance(error, PermissionError):
        print(f"Permission Error: {error}")
    elif isinstance(error, RuntimeError):
        print(f"Execution Error: {error}")
    else:
        print(f"An unexpected error occurred: {error}")
    sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main()) 