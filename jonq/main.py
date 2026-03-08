from __future__ import annotations

import sys
import os
import json
import glob as globmod
import logging
import asyncio
import time

from jonq.query_parser import tokenize_query, parse_query
from jonq.csv_utils import json_to_csv
from jonq.jq_filter import generate_jq_filter
from jonq.executor import run_jq_async, run_jq_streaming_async
from jonq.error_handler import (
    ErrorAnalyzer,
    validate_query_against_schema,
    handle_error_with_context,
    QuerySyntaxError,
)
from jonq.constants import (
    _Colors,
    USER_AGENT,
    URL_FETCH_TIMEOUT,
    WATCH_POLL_INTERVAL,
    WATCH_RETRY_INTERVAL,
    NDJSON_SNIFF_LINES,
    NDJSON_MIN_VALID,
    SCHEMA_SAMPLE_TRUNCATE,
)

logger = logging.getLogger(__name__)


def _looks_like_ndjson(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            first = f.read(1).lstrip()
            if first in ("[", "{", ""):
                if first == "[":
                    return False
                if first == "":
                    return False
            f.seek(0)
            valid = 0
            for i, raw in enumerate(f):
                line = raw.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                    valid += 1
                except json.JSONDecodeError:
                    return False
                if i >= NDJSON_SNIFF_LINES - 1:
                    break
            return valid >= NDJSON_MIN_VALID
    except OSError:
        return False


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


def _concat_glob(pattern: str) -> str:
    import tempfile

    paths = sorted(globmod.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No files matched pattern: {pattern}")
    all_items = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            all_items.extend(data)
        else:
            all_items.append(data)
    fd, tmp_path = tempfile.mkstemp(prefix="jonq_glob_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(all_items, f, separators=(",", ":"))
    return tmp_path


def _fetch_url(url: str) -> str:
    import tempfile
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=URL_FETCH_TIMEOUT) as resp:
            body = resp.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch URL: {exc}") from exc
    fd, tmp_path = tempfile.mkstemp(prefix="jonq_url_", suffix=".json")
    with os.fdopen(fd, "wb") as f:
        f.write(body)
    return tmp_path


def _type_label(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return f"array[{len(v)}]"
    if isinstance(v, dict):
        return f"object{{{len(v)}}}"
    return type(v).__name__


def _print_schema(json_file: str) -> None:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading {json_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, list):
        count = len(data)
        sample = data[0] if data else {}
        print(f"{c.BOLD}{json_file}{c.NC}  {c.DIM}({count} items, array){c.NC}")
    elif isinstance(data, dict):
        count = 1
        sample = data
        print(f"{c.BOLD}{json_file}{c.NC}  {c.DIM}(object){c.NC}")
    else:
        print(f"{c.BOLD}{json_file}{c.NC}  {c.DIM}(scalar: {_type_label(data)}){c.NC}")
        print(f"  {data}")
        return

    if not isinstance(sample, dict):
        print(f"  Items are {_type_label(sample)}, not objects.")
        return

    print(f"\n{c.BOLD}Fields:{c.NC}")
    max_key = max((len(k) for k in sample), default=0)
    for key, value in sample.items():
        tl = _type_label(value)
        preview = ""
        if isinstance(value, (str, int, float, bool)):
            preview = f"  {c.DIM}{json.dumps(value)}{c.NC}"
        elif (
            isinstance(value, list)
            and value
            and isinstance(value[0], (str, int, float, bool))
        ):
            short = json.dumps(value[:3])
            if len(value) > 3:
                short = short[:-1] + ", ...]"
            preview = f"  {c.DIM}{short}{c.NC}"
        print(f"  {c.GREEN}{key:<{max_key}}{c.NC}  {c.YELLOW}{tl}{c.NC}{preview}")

    for key, value in sample.items():
        if isinstance(value, dict):
            print(f"\n  {c.BOLD}{key}.*:{c.NC}")
            for sub_key, sub_val in value.items():
                tl = _type_label(sub_val)
                preview = ""
                if isinstance(sub_val, (str, int, float, bool)):
                    preview = f"  {c.DIM}{json.dumps(sub_val)}{c.NC}"
                print(
                    f"    {c.GREEN}{key}.{sub_key}{c.NC}  {c.YELLOW}{tl}{c.NC}{preview}"
                )

    print(f"\n{c.BOLD}Sample:{c.NC}")
    print(
        f"  {json.dumps(sample, indent=2, ensure_ascii=False)[:SCHEMA_SAMPLE_TRUNCATE]}"
    )

    print(f'\n{c.DIM}Tip: jonq {json_file} "select *" | head{c.NC}')


def _colorize_json(s: str) -> str:
    import re as _re

    c = _Colors(enabled=True)
    s = _re.sub(r'"([^"]+)"(\s*:)', f'{c.CYAN}"\\1"{c.NC}\\2', s)
    s = _re.sub(r':\s*"([^"]*)"', lambda m: f': {c.GREEN}"{m.group(1)}"{c.NC}', s)
    s = _re.sub(
        r"(?<=[\s,\[:])([-]?\d+\.?\d*(?:[eE][+-]?\d+)?)(?=[\s,\]\}])",
        f"{c.YELLOW}\\1{c.NC}",
        s,
    )
    s = _re.sub(r"\b(null)\b", f"{c.DIM}\\1{c.NC}", s)
    s = _re.sub(r"\b(true|false)\b", f"{c.MAGENTA}\\1{c.NC}", s)
    return s


def _apply_limit_to_json_string(s, n):
    try:
        data = json.loads(s)
        if isinstance(data, list):
            data = data[:n]
            return json.dumps(data, separators=(",", ":"))
    except (json.JSONDecodeError, TypeError):
        logger.debug("Failed to parse JSON for limit: %s", s[:100])
    return s


def _apply_limit_to_csv_string(s, n):
    try:
        lines = s.splitlines()
        if not lines:
            return s
        header = lines[:1]
        rows = lines[1 : 1 + max(0, n)]
        return "\n".join(header + rows)
    except (TypeError, AttributeError):
        return s


def _pretty_json_string(s):
    try:
        obj = json.loads(s)
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return s


def _run_repl(json_file: str, options: dict) -> None:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)

    print(f"{c.BOLD}jonq interactive mode{c.NC} — querying {c.BOLD}{json_file}{c.NC}")
    print(f"{c.DIM}Type a query (without jonq/filename), or 'quit' to exit.{c.NC}")
    print(f"{c.DIM}Example: select name, age if age > 30{c.NC}\n")

    while True:
        try:
            query = input(f"{c.BOLD}jonq>{c.NC} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query or query.lower() in ("quit", "exit", "q"):
            break
        try:
            result = asyncio.run(_run_query(json_file, query, options))
            if result:
                print(result)
        except SystemExit:
            pass
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)


async def _run_query(json_file: str, query: str, options: dict) -> str | None:
    validation_error = validate_query_against_schema(json_file, query)
    if validation_error:
        raise QuerySyntaxError(
            validation_error, suggestion="Use 'select *' to see available fields"
        )

    tokens = tokenize_query(query)
    (
        fields,
        condition,
        group_by,
        having,
        order_by,
        sort_direction,
        limit,
        from_path,
        distinct,
    ) = parse_query(tokens)
    jq_filter = generate_jq_filter(
        fields,
        condition,
        group_by,
        having,
        order_by,
        sort_direction,
        limit,
        from_path,
        distinct,
    )

    if options.get("show_jq"):
        return jq_filter

    if options["streaming"]:
        stdout, stderr = await run_jq_streaming_async(json_file, jq_filter)
    else:
        stdout, stderr = await run_jq_async(json_file, jq_filter)

    if stderr:
        analyzer = ErrorAnalyzer(json_file, query, jq_filter)
        raise analyzer.analyze_jq_error(stderr)

    if not stdout:
        return None

    out_text = stdout

    if options["format"] == "csv":
        out_text = json_to_csv(out_text)

    user_limit = options.get("limit")
    if user_limit is not None:
        if options["format"] == "csv":
            out_text = _apply_limit_to_csv_string(out_text, user_limit)
        else:
            out_text = _apply_limit_to_json_string(out_text, user_limit)

    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    if options["format"] == "json":
        if options.get("pretty") or (is_tty and not options.get("no_color")):
            out_text = _pretty_json_string(out_text)
        if is_tty and not options.get("no_color"):
            out_text = _colorize_json(out_text)

    return out_text.strip()


async def _watch_loop(json_file: str, query: str, options: dict) -> None:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)

    last_mtime = 0.0
    last_output = ""
    print(f"{c.DIM}Watching {json_file} — press Ctrl+C to stop{c.NC}")

    try:
        while True:
            try:
                mtime = os.path.getmtime(json_file)
            except OSError:
                await asyncio.sleep(WATCH_RETRY_INTERVAL)
                continue

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    result = await _run_query(json_file, query, options)
                    output = result or ""
                except Exception as exc:
                    output = f"Error: {exc}"

                if output != last_output:
                    last_output = output
                    if is_tty:
                        sys.stdout.write(c.CLEAR_SCREEN)
                    print(f"{c.DIM}[{time.strftime('%H:%M:%S')}] {json_file}{c.NC}")
                    print(output)

            await asyncio.sleep(WATCH_POLL_INTERVAL)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


async def _amain():
    logging.basicConfig(
        format="%(levelname)s:%(name)s:%(message)s", level=logging.WARNING
    )

    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print_help()
        sys.exit(0)

    has_select_arg = any(
        a.lower().startswith("select") for a in sys.argv[1:] if not a.startswith("-")
    )
    non_flag_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if (
        len(non_flag_args) == 1
        and not has_select_arg
        and not sys.argv[1].startswith("-")
    ):
        target = non_flag_args[0]
        if target.startswith("http://") or target.startswith("https://"):
            import tempfile

            tmp = _fetch_url(target)
            _print_schema(tmp)
            os.remove(tmp)
        elif any(c in target for c in "*?"):
            paths = sorted(globmod.glob(target))
            if not paths:
                print(f"No files matched: {target}", file=sys.stderr)
                sys.exit(1)
            _print_schema(paths[0])
        else:
            _print_schema(target)
        sys.exit(0)

    if len(sys.argv) < 3:
        print("Usage: jonq <path/json_file|url|glob|-> <query> [options]")
        print("       jonq <path/json_file>               (show schema)")
        print("       jonq -i <path/json_file>             (interactive mode)")
        print("Try 'jonq --help' for more information.")
        sys.exit(1)

    if sys.argv[1] == "-i":
        if len(sys.argv) < 3:
            print("Usage: jonq -i <path/json_file>")
            sys.exit(1)
        json_file = sys.argv[2]
        options = parse_options(sys.argv[3:])
        if not os.path.exists(json_file):
            print(f"File not found: {json_file}", file=sys.stderr)
            sys.exit(1)
        _run_repl(json_file, options)
        sys.exit(0)

    json_file = sys.argv[1]
    query = sys.argv[2]
    options = parse_options(sys.argv[3:])

    tmp_paths = []

    if json_file.startswith("http://") or json_file.startswith("https://"):
        tmp_path = _fetch_url(json_file)
        tmp_paths.append(tmp_path)
        json_file = tmp_path

    elif any(c in json_file for c in "*?") and json_file != "-":
        tmp_path = _concat_glob(json_file)
        tmp_paths.append(tmp_path)
        json_file = tmp_path

    elif json_file != "-" and os.path.isfile(json_file):
        if options.get("ndjson") or _looks_like_ndjson(json_file):
            if options.get("streaming"):
                print(
                    "NDJSON with --stream is not supported yet. Omit --stream for now."
                )
                sys.exit(2)
            import tempfile

            json_text = _slurp_ndjson(json_file)
            fd, tmp_path = tempfile.mkstemp(prefix="jonq_ndjson_", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as _tmp:
                _tmp.write(json_text)
            tmp_paths.append(tmp_path)
            json_file = tmp_path

    if sys.argv[1] == "-" and not tmp_paths:
        import tempfile

        data = sys.stdin.read()
        fd, tmp_path = tempfile.mkstemp(prefix="jonq_stdin_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as _tmp:
            _tmp.write(data)
        tmp_paths.append(tmp_path)
        json_file = tmp_path

    try:
        validate_input_file(json_file)

        if options.get("watch"):
            await _watch_loop(json_file, query, options)
            return

        result = await _run_query(json_file, query, options)

        if result:
            out_path = options.get("out")
            if out_path:
                import re

                clean = re.sub(r"\033\[[0-9;]*m", "", result)
                with open(out_path, "w", encoding="utf-8") as fp:
                    fp.write(clean + ("\n" if not clean.endswith("\n") else ""))
            else:
                print(result)

    except Exception as e:
        filter_to_show = None
        handle_error_with_context(e, json_file, query, filter_to_show)
        sys.exit(1)
    finally:
        for p in tmp_paths:
            try:
                os.remove(p)
            except OSError:
                logger.debug("Failed to remove temp file: %s", p)


def print_help():
    print("jonq - SQL-like query tool for JSON data")
    print("\nUsage:")
    print("  jonq <file|url|glob|-> <query> [options]")
    print("  jonq <file>                               Show schema/fields")
    print("  jonq -i <file>                             Interactive REPL")
    print("\nOptions:")
    print("  --format, -f csv|json   Output format (default: json)")
    print("  --stream, -s            Process large files in streaming mode")
    print("  --ndjson                Force NDJSON mode (auto-detected by default)")
    print("  --limit, -n N           Limit rows/items to N (applied post-query)")
    print("  --out, -o PATH          Write output to file")
    print("  --jq                    Print generated jq and exit")
    print("  --pretty, -p            Pretty-print JSON output")
    print("  --watch, -w             Re-run query when file changes")
    print("  --no-color              Disable colorized output")
    print("  -i <file>               Interactive query mode (REPL)")
    print("  -h, --help              Show this help message")
    print("\nInput sources:")
    print("  file.json               Local JSON file")
    print("  -                       Read from stdin")
    print("  https://api.example.com Fetch URL")
    print("  'logs/*.json'           Glob multiple files (quote the pattern!)")
    print("\nExamples:")
    print('  jonq data.json "select name, age if age > 30"')
    print("  jonq data.json                              # show schema")
    print("  jonq -i data.json                           # interactive mode")
    print('  jonq data.json "select *" --watch           # watch for changes')
    print("  jonq 'logs/*.json' \"select * if level = 'error'\"")
    print('  jonq https://api.example.com/data "select id, name"')


def parse_options(args: list[str]) -> dict:
    options = {
        "format": "json",
        "streaming": False,
        "ndjson": False,
        "limit": None,
        "out": None,
        "show_jq": False,
        "pretty": False,
        "watch": False,
        "no_color": False,
    }
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--format", "-f") and i + 1 < len(args):
            if args[i + 1].lower() == "csv":
                options["format"] = "csv"
            i += 2
        elif a in ("--stream", "-s"):
            options["streaming"] = True
            i += 1
        elif a == "--ndjson":
            options["ndjson"] = True
            i += 1
        elif a in ("--limit", "-n") and i + 1 < len(args):
            try:
                options["limit"] = int(args[i + 1])
            except ValueError:
                print(f"Invalid --limit: {args[i + 1]}")
                sys.exit(1)
            i += 2
        elif a in ("--out", "-o") and i + 1 < len(args):
            options["out"] = args[i + 1]
            i += 2
        elif a == "--jq":
            options["show_jq"] = True
            i += 1
        elif a in ("--pretty", "-p"):
            options["pretty"] = True
            i += 1
        elif a in ("--watch", "-w"):
            options["watch"] = True
            i += 1
        elif a == "--no-color":
            options["no_color"] = True
            i += 1
        else:
            print(f"Unknown option: {a}")
            sys.exit(1)
    return options


def validate_input_file(json_file: str) -> None:
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"JSON file '{json_file}' not found.")
    if not os.path.isfile(json_file):
        raise FileNotFoundError(f"'{json_file}' is not a file.")
    if not os.access(json_file, os.R_OK):
        raise PermissionError(f"Cannot read JSON file '{json_file}'.")
    if os.path.getsize(json_file) == 0:
        raise ValueError(f"JSON file '{json_file}' is empty.")


def main():
    asyncio.run(_amain())


def entrypoint():
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
