from __future__ import annotations
import logging
import re
from typing import Optional
from jonq.ast import (
    AndCondition,
    BetweenCondition,
    Condition,
    Expression,
    ExprType,
    InCondition,
    NotCondition,
    OrCondition,
    Path,
    PathType,
)
from jonq.parser import parse_path, parse_expression

logger = logging.getLogger(__name__)

_FUNC_MAP = {
    "upper": "ascii_upcase",
    "lower": "ascii_downcase",
    "length": "length",
    "round": "round",
    "abs": "fabs",
    "ceil": "ceil",
    "floor": "floor",
    "int": "tonumber | floor",
    "float": "tonumber",
    "str": "tostring",
    "string": "tostring",
    "to_number": "tonumber",
    "to_string": "tostring",
    "keys": "keys",
    "values": "values",
    "type": "type",
    "trim": 'ltrimstr(" ") | rtrimstr(" ")',
    "reverse": "reverse",
    "sort": "sort",
    "unique": "unique",
    "flatten": "flatten",
    "not_null": "values",
    "to_entries": "to_entries",
    "from_entries": "from_entries",
    "todate": "todate",
    "fromdate": "fromdate",
    "date": "todate",
    "timestamp": "fromdate",
    "ltrim": 'ltrimstr(" ")',
    "rtrim": 'rtrimstr(" ")',
    "tojson": "tojson",
    "fromjson": "fromjson",
}


def _quote(name: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return name
    return '"' + name.replace('"', r"\"") + '"'


def generate_jq_path(path: Path, context: str = "root", null_check: bool = True) -> str:
    if not path.elements:
        return "."

    result = ""
    for i, element in enumerate(path.elements):
        if element.type == PathType.FIELD:
            seg = f".{_quote(element.value)}"
            if i == 0:
                result += seg
            else:
                result += seg
        elif element.type == PathType.ARRAY:
            seg = f".{_quote(element.value)}[]?"
            if i == 0:
                result += seg
            else:
                result += seg
        elif element.type == PathType.ARRAY_INDEX:
            result += f"[{element.value}]?"

    if null_check:
        parts = result.split(".")
        for i in range(1, len(parts)):
            if "[]?" not in parts[i] and not re.search(r"\[\d+\]\?$", parts[i]):
                parts[i] = parts[i] + "?"
        result = ".".join(parts)

    return result


def generate_jq_expression(expr: Expression, context: str = "root") -> str:
    if expr.type == ExprType.FIELD:
        path = parse_path(expr.value)
        return generate_jq_path(path, context)
    elif expr.type == ExprType.AGGREGATION:
        func = expr.value
        arg = expr.args[0]

        if func == "count" and arg == "*":
            return "length"

        arg_path = parse_path(arg)
        arg_jq = generate_jq_path(arg_path, context)

        if context == "group" and "[]" in arg:
            if func == "count":
                return f"(map({arg_jq}) | length)"
            elif func == "sum":
                return f'(map({arg_jq} | select(type=="number")) | add // 0)'
            elif func == "avg":
                return (
                    f'(map({arg_jq} | select(type=="number")) '
                    f"| if length>0 then (add/length) else null end)"
                )
            elif func == "max":
                return f'(map({arg_jq} | select(type=="number")) | max?)'
            elif func == "min":
                return f'(map({arg_jq} | select(type=="number")) | min?)'

        if "[]" in arg:
            if func == "count":
                return f"([{arg_jq}] | length)"
            elif func == "sum":
                return (
                    f'([{arg_jq}] | flatten | map(select(type == "number")) | add // 0)'
                )
            elif func == "avg":
                return f'([{arg_jq}] | flatten | map(select(type == "number")) | if length > 0 then (add / length) else null end)'
            elif func == "max":
                return f'([{arg_jq}] | flatten | map(select(type == "number")) | if length > 0 then max else null end)'
            elif func == "min":
                return f'([{arg_jq}] | flatten | map(select(type == "number")) | if length > 0 then min else null end)'
            else:
                return f"([{arg_jq}] | length)"

        else:
            if context == "group":
                if func == "count":
                    return f'(map({arg_jq} | if type == "array" then length else 1 end) | add // 0)'
                elif func == "sum":
                    return f'(map({arg_jq} | if type == "array" then (map(select(type == "number")) | add // []) else select(type == "number") end) | flatten | add // 0)'
                elif func == "avg":
                    return f'(map({arg_jq} | if type == "array" then (map(select(type == "number")) | add // []) else select(type == "number") end) | flatten | if length > 0 then (add / length) else null end)'
                elif func == "max":
                    return f'(map({arg_jq} | if type == "array" then (map(select(type == "number")) | add // []) else select(type == "number") end) | flatten | if length > 0 then max else null end)'
                elif func == "min":
                    return f'(map({arg_jq} | if type == "array" then (map(select(type == "number")) | add // []) else select(type == "number") end) | flatten | if length > 0 then min else null end)'
            elif context == "array":
                if func == "count":
                    return f'(.{arg} | if type == "array" then length else 1 end)'
                elif func == "sum":
                    return f'(.{arg} | if type == "array" then (map(select(type == "number")) | add // 0) else (if type == "number" then . else 0 end) end)'
                elif func == "avg":
                    return f'(.{arg} | if type == "array" and length > 0 then (map(select(type == "number")) | add / length) else (if type == "number" then . else null end) end)'
                elif func == "max":
                    return f'(.{arg} | if type == "array" and length > 0 then (map(select(type == "number")) | max) else (if type == "number" then . else null end) end)'
                elif func == "min":
                    return f'(.{arg} | if type == "array" and length > 0 then (map(select(type == "number")) | min) else (if type == "number" then . else null end) end)'
            else:
                if func == "count":
                    return "length"
                elif func == "sum":
                    return f'([.[] | {arg_jq} | select(type == "number")] | add // 0)'
                elif func == "avg":
                    return f'([.[] | {arg_jq} | select(type == "number")] | if length > 0 then (add / length) else null end)'
                elif func == "max":
                    return f'([.[] | {arg_jq} | select(type == "number")] | if length > 0 then max else null end)'
                elif func == "min":
                    return f'([.[] | {arg_jq} | select(type == "number")] | if length > 0 then min else null end)'

    elif expr.type == ExprType.LITERAL:
        return str(expr.value)
    elif expr.type == ExprType.OPERATION:
        op = expr.value
        left = generate_jq_expression(expr.args[0], context)
        right = generate_jq_expression(expr.args[1], context)
        return f"({left} {op} {right})"
    elif expr.type == ExprType.BINARY_CONDITION:
        op = expr.value
        left = generate_jq_expression(expr.args[0], context)
        right = generate_jq_expression(expr.args[1], context)

        if op == "contains":
            return f"(({left} != null) and (({left} | tostring) | contains({right})))"
        elif op == "like":
            pattern = right.strip('"')
            if pattern.startswith("%") and pattern.endswith("%"):
                inner = pattern[1:-1]
                return f'({left} | tostring | test("{inner}"))'
            elif pattern.startswith("%"):
                suffix = pattern[1:]
                return f'({left} | tostring | endswith("{suffix}"))'
            elif pattern.endswith("%"):
                prefix = pattern[:-1]
                return f'({left} | tostring | startswith("{prefix}"))'
            else:
                return f'({left} | tostring | test("{pattern}"))'
        else:
            return f"{left} {op} {right}"

    elif expr.type == ExprType.FUNCTION:
        func = expr.value
        if func == "coalesce" and expr.args:
            parts = [generate_jq_expression(a, context) for a in expr.args]
            return "(" + " // ".join(parts) + ")"
        if func == "if_null" and expr.args and len(expr.args) == 2:
            val = generate_jq_expression(expr.args[0], context)
            default = generate_jq_expression(expr.args[1], context)
            return f"({val} // {default})"
        arg = generate_jq_expression(expr.args[0], context) if expr.args else "."
        jq_func = _FUNC_MAP.get(func, func)
        _NULL_SENSITIVE = {"todate", "fromdate", "date", "timestamp", "tonumber", "tonumber | floor"}
        if jq_func in _NULL_SENSITIVE:
            return f"(if {arg} != null then ({arg} | {jq_func}) else null end)"
        return f"({arg} | {jq_func})"

    elif expr.type == ExprType.CASE:
        from jonq.query_parser import parse_condition_string
        whens = expr.args or []
        else_val = expr.value
        parts = []
        for i, (cond_str, val_str) in enumerate(whens):
            cond_ast = parse_condition_string(cond_str)
            cond_jq = generate_jq_condition(cond_ast, context)
            val_expr = parse_expression(val_str)
            val_jq = generate_jq_expression(val_expr, context)
            if i == 0:
                parts.append(f"if {cond_jq} then {val_jq}")
            else:
                parts.append(f"elif {cond_jq} then {val_jq}")
        if else_val:
            else_expr = parse_expression(else_val)
            else_jq = generate_jq_expression(else_expr, context)
            parts.append(f"else {else_jq}")
        else:
            parts.append("else null")
        parts.append("end")
        return "(" + " ".join(parts) + ")"

    return str(expr.value)


def generate_jq_condition(
    cond: Condition
    | AndCondition
    | OrCondition
    | NotCondition
    | InCondition
    | BetweenCondition,
    context: str = "root",
) -> str:
    if isinstance(cond, AndCondition):
        left = generate_jq_condition(cond.left, context)
        right = generate_jq_condition(cond.right, context)
        return f"({left} and {right})"
    elif isinstance(cond, OrCondition):
        left = generate_jq_condition(cond.left, context)
        right = generate_jq_condition(cond.right, context)
        return f"({left} or {right})"
    elif isinstance(cond, NotCondition):
        inner = generate_jq_condition(cond.condition, context)
        return f"({inner} | not)"
    elif isinstance(cond, InCondition):
        path = parse_path(cond.field)
        path_jq = generate_jq_path(path, context)
        clauses = " or ".join(f"{path_jq} == {v}" for v in cond.values)
        return f"({clauses})"
    elif isinstance(cond, BetweenCondition):
        path = parse_path(cond.field)
        path_jq = generate_jq_path(path, context)
        return f"({path_jq} != null and {path_jq} >= {cond.low} and {path_jq} <= {cond.high})"
    elif isinstance(cond, Condition):
        return generate_jq_expression(cond.expr, context)

    return ""


def split_base_array(path: str) -> tuple[Optional[str], str]:
    if "[]" not in path:
        return None, path
    before, after = path.split("[]", 1)
    before = before.rstrip(".")
    after = after.lstrip(".")
    return before, after


def strip_prefix(path: str, prefix: str) -> str:
    needle = f"{prefix}[]"
    return path[len(needle) :].lstrip(".") if path.startswith(needle) else path


def format_field_path(field: str) -> str:
    path = parse_path(field)
    return generate_jq_path(path)


def build_jq_path(field_path: str) -> str:
    path = parse_path(field_path)
    return generate_jq_path(path)


def transform_nested_array_path(field_path: str) -> str:
    path = parse_path(field_path)
    return generate_jq_path(path, context="array")


def escape_string(s: str) -> str:
    if (s.startswith("'") and s.endswith("'")) or (
        s.startswith('"') and s.endswith('"')
    ):
        content = s[1:-1]
        escaped = content.replace('"', '\\"')
        return f'"{escaped}"'
    return s


def process_having_condition(having: str, fields: Optional[list[tuple]] = None) -> str:
    if not having:
        return ""

    aliases = set()
    if fields:
        for tup in fields:
            aliases.add(tup[-1])

    def _dot_prefix_ident(token):
        token = token.strip()
        if not token.startswith(".") and re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", token):
            if not aliases or token in aliases:
                return f".{token}"
        return token

    def _process_single(part):
        part = part.strip()
        for op in [" >= ", " <= ", " != ", " == ", " > ", " < "]:
            if op in part:
                left, right = part.split(op, 1)
                left = _dot_prefix_ident(left)
                right = right.strip()
                return f"{left}{op}{right}"
        return part

    if " and " in having:
        parts = having.split(" and ")
        return " and ".join(_process_single(p) for p in parts)

    return _process_single(having)


def make_selector_from_path(path_with_arrays: str) -> str:
    pieces = []
    remaining = path_with_arrays.lstrip(".")
    while "[]" in remaining:
        pre, remaining = remaining.split("[]", 1)
        pre = pre.lstrip(".")
        pieces.append(f".{pre}[]")
        if remaining.startswith("."):
            remaining = remaining[1:]
    return " | ".join(pieces)


def _gen_field_selector(ftype: str, data: list, base_context: str) -> Optional[str]:
    if ftype == "field":
        field, alias = data
        return (
            f'"{alias}": ({generate_jq_path(parse_path(field), base_context)} // null)'
        )
    elif ftype == "aggregation":
        func, param, alias = data
        return f'"{alias}": {generate_jq_expression(Expression(ExprType.AGGREGATION, func, [param]), base_context)}'
    elif ftype == "expression":
        expr_txt, alias = data
        return f'"{alias}": {generate_jq_expression(parse_expression(expr_txt), base_context)}'
    elif ftype == "direct_jq":
        jq_expr, alias = data
        return f'"{alias}": {jq_expr}'
    elif ftype == "function":
        func, param, alias = data
        jq_func = _FUNC_MAP.get(func, func)
        path_jq = generate_jq_path(parse_path(param), base_context)
        _NULL_SENSITIVE = {"todate", "fromdate", "date", "timestamp", "tonumber", "tonumber | floor"}
        if jq_func in _NULL_SENSITIVE:
            return f'"{alias}": (if {path_jq} != null then ({path_jq} | {jq_func}) else null end)'
        return f'"{alias}": ({path_jq} | {jq_func})'
    elif ftype == "count_distinct":
        param, alias = data
        path_jq = generate_jq_path(parse_path(param), base_context)
        return f'"{alias}": ([.[] | {path_jq}] | unique | length)'
    return None


def generate_jq_filter(
    fields,
    condition,
    group_by,
    having,
    order_by,
    sort_direction,
    limit,
    from_path=None,
    distinct=False,
):
    base_context = "root"
    base_selector = ""
    if from_path:
        if from_path == "[]":
            base_selector = ".[]"
            base_context = "array"

        elif from_path.startswith("[]"):
            nested_path = from_path[2:]
            if nested_path.startswith("."):
                nested_path = nested_path[1:]
            base_selector = f".[] | .{nested_path}[]"
            base_context = "array"

        elif "[]" in from_path:
            parts = from_path.split("[]", 1)

            if parts[0]:
                base = f".{parts[0].lstrip('.')}"
            else:
                base = "."

            if len(parts) > 1:
                rest = parts[1].lstrip(".")
            else:
                rest = ""

            base_selector = f"{base}[]"
            if rest:
                base_selector += f" | .{rest}"
            base_context = "array"

        else:
            base_selector = f".{from_path}[]"
            base_context = "array"

    has_no_from_path = not from_path
    has_group_by = bool(group_by)
    group_by_has_arrays = any("[]" in g for g in group_by) if group_by else False

    if has_no_from_path and has_group_by and group_by_has_arrays:
        implicit_base, _ = split_base_array(group_by[0])
        base_selector = make_selector_from_path(group_by[0])
        base_context = "array"

        updated_group_by = []
        for g in group_by:
            parts = g.split("[]")
            last_part = parts[-1]
            cleaned = last_part.lstrip(".")
            updated_group_by.append(cleaned)

        group_by = updated_group_by

        new_fields = []
        for tup in fields:
            if tup[0] == "field":
                path, alias = tup[1:]
                if "[]" in path:
                    path = strip_prefix(path, implicit_base).split("[]")[-1].lstrip(".")
                new_fields.append(("field", path, alias))
            elif tup[0] == "aggregation":
                func, param, alias = tup[1:]
                if "[]" in param:
                    param = strip_prefix(param, implicit_base)
                new_fields.append(("aggregation", func, param, alias))
            else:
                new_fields.append(tup)
        fields = new_fields
    if not from_path and not group_by:
        first_param_with_array = next(
            (tup[2] for tup in fields if tup[0] == "aggregation" and "[]" in tup[2]),
            None,
        )
        if first_param_with_array:
            implicit_base, _ = split_base_array(first_param_with_array)
            base_selector = f".{implicit_base}[]"
            base_context = "array"
            updated_fields = []
            for tup in fields:
                if tup[0] == "aggregation":
                    _, func, param, alias = tup
                    updated_fields.append(
                        ("aggregation", func, strip_prefix(param, implicit_base), alias)
                    )
                else:
                    updated_fields.append(tup)
            fields = updated_fields

    all_aggregations = all(ft in ("aggregation", "count_distinct") for ft, *_ in fields)
    if all_aggregations and not group_by:
        base_data = base_selector or '(if type=="array" then .[] else . end)'
        if condition:
            base_data += f" | select({condition})"

        def wrap(expr):
            stripped = expr.lstrip()
            if stripped.startswith("["):
                return expr
            else:
                return f"[ {expr} ]"

        selection = []
        for tup in fields:
            ftype = tup[0]
            if ftype == "count_distinct":
                _, param, alias = tup
                path_jq = generate_jq_path(parse_path(param), base_context)
                selection.append(
                    f'"{alias}": ([{base_data} | {path_jq}] | unique | length)'
                )
                continue
            _, func, param, alias = tup
            raw = f"{base_data} | .{param.lstrip('.')}"
            wrapped = wrap(raw)
            if func == "count" and param == "*":
                selection.append(f'"{alias}": length')
                continue
            if func == "sum":
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) | add // 0)'
                )
            elif func == "avg":
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) | if length>0 then add/length else null end)'
                )
            elif func == "min":
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) | if length>0 then min else null end)'
                )
            elif func == "max":
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) | if length>0 then max else null end)'
                )
            elif func == "count":
                selection.append(f'"{alias}": ({wrapped} | length)')
        jq_filter = f"{{ {', '.join(selection)} }}"

    elif group_by:
        group_keys = []
        for g in group_by:
            parsed = parse_path(g)
            jq_path = generate_jq_path(parsed, context="root", null_check=False)
            group_keys.append(jq_path)

        group_key = ", ".join(group_keys)
        agg_sel = []
        for ftype, *data in fields:
            if ftype == "field":
                fld, alias = data
                path = generate_jq_path(
                    parse_path(fld), context="root", null_check=False
                ).lstrip(".")
                agg_sel.append(f'"{alias}": .[0].{path}')
            elif ftype == "aggregation":
                func, param, alias = data
                expr = Expression(ExprType.AGGREGATION, func, [param])
                agg_sel.append(f'"{alias}": {generate_jq_expression(expr, "group")}')
            elif ftype == "count_distinct":
                param, alias = data
                path_jq = generate_jq_path(
                    parse_path(param), context="root", null_check=False
                )
                agg_sel.append(f'"{alias}": ([.[] | {path_jq}] | unique | length)')
            elif ftype == "function":
                func, param, alias = data
                jq_func = _FUNC_MAP.get(func, func)
                _NULL_SENSITIVE = {"todate", "fromdate", "date", "timestamp", "tonumber", "tonumber | floor"}
                if jq_func in _NULL_SENSITIVE:
                    agg_sel.append(f'"{alias}": (if .[0].{param} != null then (.[0].{param} | {jq_func}) else null end)')
                else:
                    agg_sel.append(f'"{alias}": (.[0].{param} | {jq_func})')
            elif ftype == "expression":
                expr_txt, alias = data
                expr = parse_expression(expr_txt)
                agg_sel.append(f'"{alias}": {generate_jq_expression(expr, "group")}')

        if base_selector:
            prefix = f"[ {base_selector} ] | "
        else:
            prefix = "[ .[] ] | "

        jq_filter = f"{prefix}map(select(. != null)) | group_by({group_key}) | map({{ {', '.join(agg_sel)} }})"
        if having:
            jq_filter += f" | map(select({process_having_condition(having, fields)}))"
        if order_by:
            jq_filter += f" | sort_by(.{order_by})" + (
                " | reverse" if sort_direction == "desc" else ""
            )
        if limit:
            jq_filter += f" | .[0:{limit}]"
    else:
        if fields == [("field", "*", "*")]:
            if from_path:
                jq_filter = f"[{base_selector}]"
            else:
                jq_filter = "."
            if condition:
                if from_path:
                    jq_filter = f"[{base_selector} | select({condition})]"
                else:
                    jq_filter = f'if type=="array" then [.[] | select({condition})] elif type=="object" then if {condition} then [.] else [] end else . end'
            if distinct:
                jq_filter += " | unique"
            if order_by:
                jq_filter += f" | sort_by(.{order_by})" + (
                    " | reverse" if sort_direction == "desc" else ""
                )
            if limit:
                jq_filter += f" | .[0:{limit}]"

        elif (
            not any(ft[0] in ("field", "function", "count_distinct") for ft in fields)
            and not from_path
            and not group_by
        ):
            sel = []
            for ftype, *data in fields:
                s = _gen_field_selector(ftype, data, base_context)
                if s:
                    sel.append(s)
            map_filter = f"{{ {', '.join(sel)} }}"
            has_aggregation = any(ft[0] == "aggregation" for ft in fields)
            if has_aggregation:
                jq_filter = f"[{map_filter}]"
            else:
                jq_filter = (
                    f'if type=="array" then . | map({map_filter}) '
                    f'elif type=="object" then [{map_filter}] '
                    f"else [] end"
                )
        else:
            sel = []
            for ftype, *data in fields:
                s = _gen_field_selector(ftype, data, base_context)
                if s:
                    sel.append(s)
            map_filter = f"{{ {', '.join(sel)} }}"
            if from_path:
                body = (
                    f"{base_selector} | "
                    + ("select({}) | ".format(condition) if condition else "")
                    + map_filter
                )
                jq_filter = f"[ {body} ]"
            else:
                if condition:
                    jq_filter = (
                        f'if type=="array" then . | map(select({condition}) | {map_filter}) '
                        f'elif type=="object" then [select({condition}) | {map_filter}] '
                        f'elif type=="number" then if {condition} then [{{"value":.}}] else [] end '
                        f'elif type=="string" then if {condition} then [{{"value":.}}] else [] end '
                        f"else [] end"
                    )
                else:
                    jq_filter = (
                        f'if type=="array" then . | map({map_filter}) '
                        f'elif type=="object" then [{map_filter}] '
                        f'elif type=="number" then [{{"value":.}}] '
                        f'elif type=="string" then [{{"value":.}}] '
                        f"else [] end"
                    )
            if distinct:
                jq_filter += " | unique"
            if order_by:
                jq_filter += f" | sort_by(.{order_by})" + (
                    " | reverse" if sort_direction == "desc" else ""
                )
            if limit:
                jq_filter += f" | .[0:{limit}]"
    logging.info(f"Generated jq filter: {jq_filter}")
    return jq_filter
