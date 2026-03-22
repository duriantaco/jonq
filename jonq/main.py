from __future__ import annotations

import argparse
import sys
import os
import json
import glob as globmod
import logging
import asyncio
import time
import subprocess
from collections import OrderedDict

from jonq.api import compile_query, execute_async
from jonq.error_handler import handle_error_with_context
from jonq.constants import (
    _Colors,
    VERSION,
    USER_AGENT,
    URL_FETCH_TIMEOUT,
    WATCH_POLL_INTERVAL,
    WATCH_RETRY_INTERVAL,
    NDJSON_SNIFF_LINES,
    NDJSON_MIN_VALID,
    SCHEMA_SAMPLE_TRUNCATE,
    SCHEMA_PATH_SAMPLE_ROWS,
    SCHEMA_PATH_MAX_DEPTH,
    SCHEMA_PATH_PREVIEW_ITEMS,
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


def _sample_json_for_schema(json_file: str):
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            first = " "
            while first.isspace():
                first = f.read(1)
                if first == "":
                    return "empty", None
    except OSError as exc:
        print(f"Error reading {json_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    if first == "[":
        try:
            proc = subprocess.Popen(
                ["jq", "-c", ".[]", json_file],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            samples = []
            for i, line in enumerate(proc.stdout):
                if i >= SCHEMA_PATH_SAMPLE_ROWS:
                    break
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
            stderr = proc.stderr.read().strip()
            proc.terminate()
            proc.wait(timeout=1)
            if proc.returncode not in (0, -15):
                raise RuntimeError(stderr or "jq failed while sampling array")
            return "array", samples
        except Exception:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"Error reading {json_file}: {exc}", file=sys.stderr)
                sys.exit(1)
            return "array", data[:SCHEMA_PATH_SAMPLE_ROWS] if isinstance(data, list) else []

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error reading {json_file}: {exc}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, dict):
        return "object", data
    return "scalar", data


def _array_type_label(values: list) -> str:
    if not values:
        return "array[empty]"
    elem_types = []
    for value in values[:SCHEMA_PATH_PREVIEW_ITEMS]:
        t = _type_label(value)
        if t not in elem_types:
            elem_types.append(t)
    return f"array[{' | '.join(elem_types)}]"


def _preview_value(value) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list) and value and all(
        isinstance(v, (str, int, float, bool)) or v is None
        for v in value[:SCHEMA_PATH_PREVIEW_ITEMS]
    ):
        preview_items = value[:SCHEMA_PATH_PREVIEW_ITEMS]
        preview = json.dumps(preview_items, ensure_ascii=False)
        if len(value) > SCHEMA_PATH_PREVIEW_ITEMS:
            preview = preview[:-1] + ", ...]"
        return preview
    return ""


def _add_path_record(path_map, path: str, value) -> None:
    if not path:
        return

    if isinstance(value, list):
        type_label = _array_type_label(value)
    elif isinstance(value, dict):
        type_label = "object"
    else:
        type_label = _type_label(value)

    entry = path_map.setdefault(path, {"types": [], "preview": ""})
    if type_label not in entry["types"]:
        entry["types"].append(type_label)

    preview = _preview_value(value)
    if preview and not entry["preview"]:
        entry["preview"] = preview


def _walk_schema_paths(value, path: str, path_map, depth: int) -> None:
    if depth > SCHEMA_PATH_MAX_DEPTH:
        return

    if isinstance(value, dict):
        _add_path_record(path_map, path, value)
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            _walk_schema_paths(child, child_path, path_map, depth + 1)
        return

    if isinstance(value, list):
        _add_path_record(path_map, path, value)
        item_path = f"{path}[]" if path else ""
        for child in value[:SCHEMA_PATH_PREVIEW_ITEMS]:
            if isinstance(child, (dict, list)):
                _walk_schema_paths(child, item_path, path_map, depth + 1)
        return

    _add_path_record(path_map, path, value)


def _collect_schema_paths(sample):
    paths = OrderedDict()
    if isinstance(sample, list):
        for item in sample:
            _walk_schema_paths(item, "", paths, 0)
    elif isinstance(sample, dict):
        _walk_schema_paths(sample, "", paths, 0)
    return paths


def _print_schema(json_file: str) -> None:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)

    root_kind, sample = _sample_json_for_schema(json_file)

    if root_kind == "empty":
        print(f"{c.BOLD}{json_file}{c.NC}  {c.DIM}(empty){c.NC}")
        return

    if root_kind == "scalar":
        print(
            f"{c.BOLD}{json_file}{c.NC}  {c.DIM}(scalar: {_type_label(sample)}){c.NC}"
        )
        print(f"  {sample}")
        return

    if root_kind == "array":
        sample_count = len(sample)
        print(
            f"{c.BOLD}{json_file}{c.NC}  {c.DIM}(array, sampled {sample_count} item{'s' if sample_count != 1 else ''}){c.NC}"
        )
        sample_for_display = sample[0] if sample else []
    else:
        print(f"{c.BOLD}{json_file}{c.NC}  {c.DIM}(object){c.NC}")
        sample_for_display = sample

    path_map = _collect_schema_paths(sample)
    if not path_map:
        print("  No object-like paths found in sample.")
        return

    print(f"\n{c.BOLD}Paths:{c.NC}")
    max_key = max((len(k) for k in path_map), default=0)
    for key, info in path_map.items():
        type_label = " | ".join(info["types"])
        preview = f"  {c.DIM}{info['preview']}{c.NC}" if info["preview"] else ""
        print(
            f"  {c.GREEN}{key:<{max_key}}{c.NC}  {c.YELLOW}{type_label}{c.NC}{preview}"
        )

    print(f"\n{c.BOLD}Sample:{c.NC}")
    sample_json = json.dumps(sample_for_display, indent=2, ensure_ascii=False)
    print(f"  {sample_json[:SCHEMA_SAMPLE_TRUNCATE]}")

    first_paths = list(path_map)[:2]
    if first_paths:
        example = ", ".join(first_paths)
        print(f'\n{c.DIM}Tip: jonq {json_file} "select {example}"{c.NC}')


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


def _pretty_json_string(s):
    try:
        obj = json.loads(s)
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return s


def _setup_repl_readline(json_file: str) -> None:
    """Set up readline with history and tab completion for field names."""
    try:
        import readline
    except ImportError:
        return

    history_file = os.path.expanduser("~/.jonq_history")
    try:
        readline.read_history_file(history_file)
        readline.set_history_length(500)
    except (FileNotFoundError, OSError):
        pass

    import atexit
    atexit.register(lambda: readline.write_history_file(history_file))

    # Build completion words from schema
    completions = _build_repl_completions(json_file)

    def completer(text, state):
        matches = [w for w in completions if w.startswith(text)]
        return matches[state] if state < len(matches) else None

    readline.set_completer(completer)
    readline.set_completer_delims(" \t\n,")
    readline.parse_and_bind("tab: complete")


def _build_repl_completions(json_file: str) -> list[str]:
    """Build completion list from JSON schema + keywords."""
    keywords = [
        "select", "if", "from", "group", "by", "having", "sort", "asc", "desc",
        "limit", "distinct", "and", "or", "not", "in", "like", "between",
        "contains", "as", "case", "when", "then", "else", "end", "is", "null",
        "coalesce",
        "count", "sum", "avg", "min", "max",
        "upper", "lower", "length", "round", "abs", "ceil", "floor",
        "int", "float", "str", "type", "keys", "values", "trim",
        "todate", "fromdate", "date", "tojson", "fromjson",
    ]

    field_names = []
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            sample = data[0]
        elif isinstance(data, dict):
            sample = data
        else:
            sample = None
        if isinstance(sample, dict):
            paths = _collect_schema_paths([sample] if isinstance(data, list) else sample)
            field_names = list(paths.keys())
    except Exception:
        pass

    return keywords + field_names


def _run_repl(json_file: str, options: dict) -> None:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)

    _setup_repl_readline(json_file)

    print(f"{c.BOLD}jonq interactive mode{c.NC} — querying {c.BOLD}{json_file}{c.NC}")
    print(f"{c.DIM}Type a query, or 'quit' to exit. Tab completes field names.{c.NC}")
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


def _explain_query(compiled) -> str:
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)
    parts = []
    parts.append(f"{c.BOLD}Query:{c.NC} {compiled.query}")
    parts.append("")

    parts.append(f"{c.BOLD}Parsed:{c.NC}")
    field_strs = []
    for tup in compiled.fields:
        ftype = tup[0]
        if ftype == "field":
            _, field, alias = tup
            field_strs.append(f"  {field}" + (f" as {alias}" if alias != field.split('.')[-1] else ""))
        elif ftype == "aggregation":
            _, func, param, alias = tup
            field_strs.append(f"  {func}({param}) as {alias}")
        elif ftype == "function":
            _, func, param, alias = tup
            field_strs.append(f"  {func}({param}) as {alias}")
        elif ftype == "expression":
            _, expr, alias = tup
            field_strs.append(f"  {expr} as {alias}")
        elif ftype == "count_distinct":
            _, param, alias = tup
            field_strs.append(f"  count(distinct {param}) as {alias}")
    parts.append(f"  {c.CYAN}Fields:{c.NC}")
    for s in field_strs:
        parts.append(f"  {s}")

    if compiled.from_path:
        parts.append(f"  {c.CYAN}From:{c.NC} {compiled.from_path}")
    if compiled.condition:
        parts.append(f"  {c.CYAN}Condition:{c.NC} {compiled.condition}")
    if compiled.group_by:
        parts.append(f"  {c.CYAN}Group by:{c.NC} {', '.join(compiled.group_by)}")
    if compiled.having:
        parts.append(f"  {c.CYAN}Having:{c.NC} {compiled.having}")
    if compiled.order_by:
        parts.append(f"  {c.CYAN}Sort:{c.NC} {compiled.order_by} {compiled.sort_direction}")
    if compiled.limit:
        parts.append(f"  {c.CYAN}Limit:{c.NC} {compiled.limit}")
    if compiled.distinct:
        parts.append(f"  {c.CYAN}Distinct:{c.NC} yes")

    parts.append("")
    parts.append(f"{c.BOLD}Generated jq:{c.NC}")
    parts.append(f"  {c.GREEN}{compiled.jq_filter}{c.NC}")
    return "\n".join(parts)


def _print_timing(t_start: float, t_parse: float, t_exec: float, t_format: float) -> None:
    parse_ms = (t_parse - t_start) * 1000
    exec_ms = (t_exec - t_parse) * 1000
    fmt_ms = (t_format - t_exec) * 1000
    total_ms = (t_format - t_start) * 1000
    print(
        f"parse: {parse_ms:.1f}ms | execute: {exec_ms:.1f}ms | format: {fmt_ms:.1f}ms | total: {total_ms:.1f}ms",
        file=sys.stderr,
    )


def _json_to_yaml(json_text: str) -> str:
    try:
        import yaml
        data = json.loads(json_text)
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False).rstrip()
    except ImportError:
        return _json_to_yaml_simple(json_text)
    except (json.JSONDecodeError, TypeError):
        return json_text


def _json_to_yaml_simple(json_text: str) -> str:
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, TypeError):
        return json_text

    lines = []
    _yaml_dump(data, lines, indent=0)
    return "\n".join(lines)


def _yaml_dump(obj, lines: list, indent: int) -> None:
    prefix = "  " * indent
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, (dict, list)):
                lines.append(f"{prefix}{key}:")
                _yaml_dump(val, lines, indent + 1)
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(val)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                first = True
                for key, val in item.items():
                    marker = "- " if first else "  "
                    first = False
                    if isinstance(val, (dict, list)):
                        lines.append(f"{prefix}{marker}{key}:")
                        _yaml_dump(val, lines, indent + 2)
                    else:
                        lines.append(f"{prefix}{marker}{key}: {_yaml_scalar(val)}")
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(obj)}")


def _yaml_scalar(val) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, str):
        if any(c in val for c in ":#{}[]|>&*!%@`"):
            return f'"{val}"'
        return val
    return str(val)


def _generate_completions(shell: str) -> str:
    if shell == "bash":
        return '''# jonq bash completion
# Add to ~/.bashrc: eval "$(jonq --completions bash)"
_jonq_completions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local opts="-i -f -t -s -n -o -p -w --format --table --stream --ndjson --limit --out --jq --explain --time --pretty --watch --follow --no-color --version --help --completions"
    local keywords="select if from group by having sort asc desc limit distinct and or not in like between contains as case when then else end is null coalesce count sum avg min max upper lower length round abs ceil floor int float str type keys values trim todate fromdate date tojson fromjson"

    if [[ "${cur}" == -* ]]; then
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
    elif [[ "${COMP_CWORD}" == 1 ]]; then
        COMPREPLY=($(compgen -f -X '!*.json' -- "${cur}") $(compgen -f -X '!*.jsonl' -- "${cur}"))
    else
        COMPREPLY=($(compgen -W "${keywords}" -- "${cur}"))
    fi
}
complete -F _jonq_completions jonq'''
    elif shell == "zsh":
        return '''# jonq zsh completion
# Add to ~/.zshrc: eval "$(jonq --completions zsh)"
_jonq() {
    local -a opts keywords
    opts=(
        '-i:Interactive mode'
        '-f:Output format'
        '-t:Table output'
        '-s:Streaming mode'
        '-n:Limit rows'
        '-o:Output file'
        '-p:Pretty print'
        '-w:Watch mode'
        '--follow:Follow stdin'
        '--jq:Show jq filter'
        '--explain:Explain query'
        '--time:Show timing'
        '--no-color:No color'
        '--completions:Shell completions'
    )
    keywords=(select if from group by having sort asc desc limit distinct and or not in like between contains as case when then else end is null coalesce count sum avg min max upper lower length round abs ceil floor int float str type keys values trim todate fromdate)

    if [[ "${words[2]}" == -* ]]; then
        _describe 'options' opts
    elif [[ ${CURRENT} -eq 2 ]]; then
        _files -g '*.json(|l)'
    else
        compadd "${keywords[@]}"
    fi
}
compdef _jonq jonq'''
    elif shell == "fish":
        return '''# jonq fish completion
# Add to ~/.config/fish/completions/jonq.fish
complete -c jonq -s i -l interactive -d 'Interactive mode' -r -F
complete -c jonq -s f -l format -d 'Output format' -x -a 'json csv table yaml'
complete -c jonq -s t -l table -d 'Table output'
complete -c jonq -s s -l stream -d 'Streaming mode'
complete -c jonq -s n -l limit -d 'Limit rows' -x
complete -c jonq -s o -l out -d 'Output file' -r -F
complete -c jonq -s p -l pretty -d 'Pretty print'
complete -c jonq -s w -l watch -d 'Watch mode'
complete -c jonq -l follow -d 'Follow stdin'
complete -c jonq -l jq -d 'Show jq filter'
complete -c jonq -l explain -d 'Explain query'
complete -c jonq -l time -d 'Show timing'
complete -c jonq -l no-color -d 'No color'
complete -c jonq -l completions -d 'Shell completions' -x -a 'bash zsh fish'
complete -c jonq -l version -d 'Show version\''''
    return ""


async def _follow_stdin(query: str, options: dict) -> None:
    """Stream NDJSON from stdin, applying the query to each line."""
    from jonq.api import compile_query as _compile
    from jonq.executor import run_jq

    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    c = _Colors(is_tty)

    compiled = _compile(query)
    jq_filter = compiled.jq_filter

    print(f"{c.DIM}Following stdin — press Ctrl+C to stop{c.NC}", file=sys.stderr)

    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError:
                continue

            wrapped = f"[{line}]"
            try:
                stdout, stderr = run_jq(jq_filter, wrapped)
                if stderr:
                    continue
                if stdout and stdout.strip():
                    result = stdout.strip()
                    if result in ("[]", "null", ""):
                        continue
                    if options["format"] == "table":
                        from jonq.table_utils import json_to_table
                        result = json_to_table(result, color=is_tty and not options.get("no_color"))
                    elif options["format"] == "yaml":
                        result = _json_to_yaml(result)
                    elif is_tty and not options.get("no_color"):
                        result = _pretty_json_string(result)
                        result = _colorize_json(result)
                    print(result, flush=True)
            except Exception:
                continue
    except KeyboardInterrupt:
        pass


async def _run_query(json_file: str, query: str, options: dict) -> str | None:
    t_start = time.monotonic()
    compiled = compile_query(query)
    t_parse = time.monotonic()

    if options.get("show_jq"):
        return compiled.jq_filter

    if options.get("explain"):
        return _explain_query(compiled)

    exec_format = "json" if options["format"] in ("table", "yaml") else options["format"]

    result = await execute_async(
        json_file,
        compiled,
        format=exec_format,
        streaming=options["streaming"],
        limit=options.get("limit"),
        validate=True,
    )
    t_exec = time.monotonic()

    if not result.text:
        if options.get("show_time"):
            _print_timing(t_start, t_parse, t_exec, time.monotonic())
        return None

    out_text = result.text

    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    if options["format"] == "table":
        from jonq.table_utils import json_to_table

        use_color = is_tty and not options.get("no_color")
        out_text = json_to_table(out_text, color=use_color)
    elif options["format"] == "yaml":
        out_text = _json_to_yaml(out_text)
    elif options["format"] == "json":
        if options.get("pretty") or (is_tty and not options.get("no_color")):
            out_text = _pretty_json_string(out_text)
        if is_tty and not options.get("no_color"):
            out_text = _colorize_json(out_text)

    t_format = time.monotonic()
    if options.get("show_time"):
        _print_timing(t_start, t_parse, t_exec, t_format)

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


async def _amain(argv: list[str] | None = None):
    logging.basicConfig(
        format="%(levelname)s:%(name)s:%(message)s", level=logging.WARNING
    )

    parser = _build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "completions", None):
        print(_generate_completions(args.completions))
        return

    if args.interactive and (args.source is not None or args.query is not None):
        parser.error("--interactive does not accept positional source/query arguments.")

    options = _options_from_args(args)

    if args.interactive:
        json_file = args.interactive
        if not os.path.exists(json_file):
            print(f"File not found: {json_file}", file=sys.stderr)
            sys.exit(1)
        _run_repl(json_file, options)
        return

    stdin_is_pipe = not sys.stdin.isatty()

    if args.source is None and args.query is None:
        if stdin_is_pipe:
            parser.print_usage(sys.stderr)
            print("Pipe detected but no query given. Usage: ... | jonq \"select ...\"", file=sys.stderr)
            sys.exit(1)
        parser.print_usage(sys.stderr)
        print("Try 'jonq --help' for more information.", file=sys.stderr)
        sys.exit(1)

    if stdin_is_pipe and args.source is not None and args.query is None:
        if not os.path.exists(args.source):
            args.query = args.source
            args.source = "-"

    if args.source is None:
        parser.print_usage(sys.stderr)
        print("Try 'jonq --help' for more information.", file=sys.stderr)
        sys.exit(1)

    if args.query is None:
        _show_schema_for_target(args.source)
        return

    json_file = args.source
    query = args.query

    if options.get("follow"):
        if json_file != "-" and not stdin_is_pipe:
            print("--follow requires piped stdin. Usage: ... | jonq --follow \"select ...\"", file=sys.stderr)
            sys.exit(1)
        await _follow_stdin(query, options)
        return

    tmp_paths: list[str] = []

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

    if json_file == "-" and not tmp_paths:
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
        handle_error_with_context(e, json_file, query, None)
        sys.exit(1)
    finally:
        for p in tmp_paths:
            try:
                os.remove(p)
            except OSError:
                logger.debug("Failed to remove temp file: %s", p)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jonq",
        description="SQL-like query tool for JSON data",
        epilog=(
            "Examples:\n"
            '  jonq data.json "select name, age if age > 30"\n'
            '  jonq data.json "select name, age" -t\n'
            "  jonq data.json\n"
            "  jonq -i data.json\n"
            '  curl api.example.com/data | jonq "select id, name"\n'
            "  tail -f app.log | jonq --follow \"select level, msg if level = 'error'\"\n"
            '  jonq data.json "select *" --watch\n'
            "  jonq 'logs/*.json' \"select * if level = 'error'\""
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Local JSON file, URL, glob, or '-' for stdin",
    )
    parser.add_argument("query", nargs="?", help="jonq query string")
    parser.add_argument(
        "-i",
        "--interactive",
        metavar="FILE",
        help="Interactive query mode (REPL)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "csv", "table", "yaml"),
        default="json",
        help="Output format (json, csv, table, yaml)",
    )
    parser.add_argument(
        "-t",
        "--table",
        action="store_true",
        help="Shorthand for --format table",
    )
    parser.add_argument(
        "-s",
        "--stream",
        dest="streaming",
        action="store_true",
        help="Process large files in streaming mode",
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="Force NDJSON mode (auto-detected by default)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        help="Limit rows/items after the query runs",
    )
    parser.add_argument("-o", "--out", help="Write output to file")
    parser.add_argument(
        "--jq",
        dest="show_jq",
        action="store_true",
        help="Print generated jq and exit",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show parsed query breakdown and generated jq filter",
    )
    parser.add_argument(
        "--time",
        dest="show_time",
        action="store_true",
        help="Print execution timing to stderr",
    )
    parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="Re-run query when the file changes",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colorized output",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Stream NDJSON from stdin line-by-line, applying the query to each object",
    )
    parser.add_argument(
        "--completions",
        choices=("bash", "zsh", "fish"),
        metavar="SHELL",
        help="Print shell completion script and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser


def _options_from_args(args: argparse.Namespace) -> dict:
    fmt = args.format
    if getattr(args, "table", False):
        fmt = "table"
    return {
        "format": fmt,
        "streaming": args.streaming,
        "ndjson": args.ndjson,
        "limit": args.limit,
        "out": args.out,
        "show_jq": args.show_jq,
        "explain": getattr(args, "explain", False),
        "show_time": getattr(args, "show_time", False),
        "pretty": args.pretty,
        "watch": args.watch,
        "no_color": args.no_color,
        "follow": getattr(args, "follow", False),
    }


def _show_schema_for_target(target: str) -> None:
    if target.startswith("http://") or target.startswith("https://"):
        tmp = _fetch_url(target)
        try:
            _print_schema(tmp)
        finally:
            os.remove(tmp)
        return

    if any(c in target for c in "*?"):
        paths = sorted(globmod.glob(target))
        if not paths:
            print(f"No files matched: {target}", file=sys.stderr)
            sys.exit(1)
        _print_schema(paths[0])
        return

    _print_schema(target)


def print_help():
    _build_parser().print_help()


def parse_options(args: list[str]) -> dict:
    parsed = _build_parser().parse_args(["placeholder.json", "select *", *args])
    return _options_from_args(parsed)


def validate_input_file(json_file: str) -> None:
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"JSON file '{json_file}' not found.")
    if not os.path.isfile(json_file):
        raise FileNotFoundError(f"'{json_file}' is not a file.")
    if not os.access(json_file, os.R_OK):
        raise PermissionError(f"Cannot read JSON file '{json_file}'.")
    if os.path.getsize(json_file) == 0:
        raise ValueError(f"JSON file '{json_file}' is empty.")


def main(argv: list[str] | None = None):
    asyncio.run(_amain(argv))


def entrypoint():
    main()


if __name__ == "__main__":
    main()
