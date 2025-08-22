import sys
import os
import json
import logging
import asyncio

from jonq.query_parser import tokenize_query, parse_query
from jonq.csv_utils import json_to_csv
from jonq.jq_filter import generate_jq_filter
from jonq.executor import run_jq_async, run_jq_streaming_async
from jonq.error_handler import (
    ErrorAnalyzer, validate_query_against_schema,
    handle_error_with_context, QuerySyntaxError
)

logger = logging.getLogger(__name__)

def _slurp_ndjson(json_file):
    if json_file == "-":
        src = sys.stdin
        close_needed = False
    else:
        src = open(json_file, "r", encoding="utf-8")
        close_needed = True
    try:
        parts = []
        for raw in src:
            line = raw.strip()
            if line:
                parts.append(line)
        return "[" + ",".join(parts) + "]"
    finally:
        if close_needed:
            src.close()

def _apply_limit_to_json_string(s, n):
    try:
        data = json.loads(s)
        if isinstance(data, list):
            data = data[:n]
            return json.dumps(data, separators=(",", ":"))
    except Exception:
        pass
    return s

def _apply_limit_to_csv_string(s, n):
    try:
        lines = s.splitlines()
        if not lines:
            return s
        header = lines[:1]
        rows = lines[1:1 + max(0, n)]
        return "\n".join(header + rows)
    except Exception:
        return s

def _pretty_json_string(s):
    try:
        obj = json.loads(s)
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return s

async def _amain():
    logging.basicConfig(
        format='%(levelname)s:%(name)s:%(message)s',
        level=logging.INFO
    )

    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print_help()
        sys.exit(0)

    if len(sys.argv) < 3:
        print("Usage: jonq <path/json_file|-> <query> [options]")
        print("Try 'jonq --help' for more information.")
        sys.exit(1)

    json_file = sys.argv[1]
    query = sys.argv[2]
    options = parse_options(sys.argv[3:])

    tmp_paths = []

    if options.get('ndjson'):
        if options.get('streaming'):
            print("NDJSON with --stream is not supported yet. Omit --stream for now.")
            sys.exit(2)
        import tempfile
        json_text = _slurp_ndjson(json_file)
        fd, tmp_path = tempfile.mkstemp(prefix="jonq_ndjson_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as _tmp:
            _tmp.write(json_text)
        tmp_paths.append(tmp_path)
        json_file = tmp_path

    elif json_file == "-":
        import tempfile
        data = sys.stdin.read()
        fd, tmp_path = tempfile.mkstemp(prefix="jonq_stdin_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as _tmp:
            _tmp.write(data)
        tmp_paths.append(tmp_path)
        json_file = tmp_path

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

        if options.get('show_jq'):
            print(jq_filter)
            sys.exit(0)

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
            out_text = stdout

            if options['format'] == "csv":
                out_text = json_to_csv(out_text, use_fast=options.get('use_fast', False))

            user_limit = options.get('limit')
            if user_limit is not None:
                if options['format'] == "csv":
                    out_text = _apply_limit_to_csv_string(out_text, user_limit)
                else:
                    out_text = _apply_limit_to_json_string(out_text, user_limit)

            if options.get('pretty') and options['format'] == "json":
                out_text = _pretty_json_string(out_text)

            out_path = options.get('out')
            if out_path:
                with open(out_path, "w", encoding="utf-8") as fp:
                    fp.write(out_text.strip() + ("\n" if not out_text.endswith("\n") else ""))
            else:
                print(out_text.strip())


        if 'tmp_paths' in locals():
            for p in tmp_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass

    except Exception as e:
        filter_to_show = jq_filter if 'jq_filter' in locals() else None
        handle_error_with_context(e, json_file, query, filter_to_show)

        if 'tmp_paths' in locals():
            for p in tmp_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass
        sys.exit(1)

def print_help():
    print("jonq - SQL-like query tool for JSON data")
    print("\nUsage: jonq <path/json_file|-> <query> [options]")
    print("\nOptions:")
    print("  --format, -f csv|json   Output format (default: json)")
    print("  --stream, -s            Process large files in streaming mode (for arrays)")
    print("  --ndjson                Treat input as one JSON object per line")
    print("  --limit, -n N           Limit rows/items to N (applied post-query)")
    print("  --out, -o PATH          Write output to file")
    print("  --jq                    Print generated jq and exit")
    print("  --pretty, -p            Pretty-print JSON output")
    print("  -h, --help              Show this help message")
    print("\nExamples:")
    print("  jonq data.json \"select * from []\"")
    print("  jonq data.json \"select name, age from [] if age > 30\" -n 100 -o out.json")
    print("  jonq data.json \"select * from []\" --jq")

def parse_options(args):
    options = {
        'format': 'json',
        'streaming': False,
        'use_fast': False,
        'ndjson': False,
        'limit': None,
        'out': None,
        'show_jq': False,
        'pretty': False,
    }
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--format", "-f") and i + 1 < len(args):
            if args[i + 1].lower() == "csv":
                options['format'] = "csv"
            i += 2
        elif a in ("--stream", "-s"):
            options['streaming'] = True
            i += 1
        elif a == "--ndjson":
            options['ndjson'] = True
            i += 1
        elif a in ("--limit", "-n") and i + 1 < len(args):
            try:
                options['limit'] = int(args[i + 1])
            except ValueError:
                print(f"Invalid --limit: {args[i + 1]}")
                sys.exit(1)
            i += 2
        elif a in ("--out", "-o") and i + 1 < len(args):
            options['out'] = args[i + 1]
            i += 2
        elif a == "--jq":
            options['show_jq'] = True
            i += 1
        elif a in ("--pretty", "-p"):
            options['pretty'] = True
            i += 1
        else:
            print(f"Unknown option: {a}")
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

def main():
    asyncio.run(_amain())

def entrypoint():
    asyncio.run(_amain())

if __name__ == '__main__':
    main()