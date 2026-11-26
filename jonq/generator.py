from __future__ import annotations
from dataclasses import dataclass, replace
import json
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
    PathElement,
    PathType,
    Predicate,
)
from jonq.parser import _QUOTED_KEY, contains_aggregate, parse_path, parse_expression, resolve_from_path

logger = logging.getLogger(__name__)
_PATH_ARRAYS = re.compile(rf"(?:{_QUOTED_KEY.pattern})|(?P<array>\[\])")

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
    return json.dumps(name)


def generate_jq_path(path: Path, context: str = "root", null_check: bool = True) -> str:
    base = "$jonq_parent" if path.from_parent else ""
    if not path.elements:
        return base or "."

    result = base
    for i, element in enumerate(path.elements):
        if element.type == PathType.FIELD:
            result += f".{_quote(element.value)}"
            indexed = (
                i + 1 < len(path.elements)
                and path.elements[i + 1].type == PathType.ARRAY_INDEX
            )
            if null_check and not indexed:
                result += "?"
        elif element.type == PathType.ARRAY:
            field = f".{_quote(element.value)}" if element.value else ""
            result += f"{field or ('.' if not result else '')}[]?"
        elif element.type == PathType.ARRAY_INDEX:
            result += f"{'.' if not result else ''}[{element.value}]?"

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
        has_array = any(element.type == PathType.ARRAY for element in arg_path.elements)

        if context == "aggregate":
            if func == "count":
                return f"([.[] | {arg_jq}] | length)"
            numeric = f"[.[] | {arg_jq} | numbers]"
            if func == "sum":
                return f"({numeric} | add // 0)"
            if func == "avg":
                return f"({numeric} | if length > 0 then add / length else null end)"
            return f"({numeric} | {func})"

        if context == "group" and has_array:
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

        if has_array:
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
                    return (
                        f'(first({arg_jq}, null) | if type == "array" then length '
                        'elif . == null then 0 else 1 end)'
                    )
                elif func == "sum":
                    return f'({arg_jq} | if type == "array" then (map(select(type == "number")) | add // 0) else (if type == "number" then . else 0 end) end)'
                elif func == "avg":
                    return f'({arg_jq} | if type == "array" then (map(numbers) | if length > 0 then add / length else null end) else (if type == "number" then . else null end) end)'
                elif func == "max":
                    return f'({arg_jq} | if type == "array" then (map(numbers) | max) else (if type == "number" then . else null end) end)'
                elif func == "min":
                    return f'({arg_jq} | if type == "array" then (map(numbers) | min) else (if type == "number" then . else null end) end)'
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
        if context in {"aggregate", "group"} and contains_aggregate(expr):
            return (
                f"(({left}) as $left | ({right}) as $right | "
                f"if $left == null or $right == null then null else $left {op} $right end)"
            )
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
            if op in {"<", "<=", ">", ">="}:
                left_expr, right_expr = expr.args
                if _is_numeric_literal(right_expr):
                    return f'(({left} | type) == "number" and {left} {op} {right})'
                if _is_numeric_literal(left_expr):
                    return f'(({right} | type) == "number" and {left} {op} {right})'
            return f"{left} {op} {right}"

    elif expr.type == ExprType.FUNCTION:
        func = expr.value
        if func in {"coalesce", "if_null"} and expr.args:
            parts = [generate_jq_expression(a, context) for a in expr.args]
            return f"(first((({', '.join(parts)}) | select(. != null)), null))"
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


def _is_numeric_literal(expr: Expression) -> bool:
    return expr.type == ExprType.LITERAL and bool(
        re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", str(expr.value))
    )


def generate_jq_condition(
    cond: Predicate,
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
    for match in _PATH_ARRAYS.finditer(path):
        if match.group("array"):
            return path[:match.start()].rstrip("."), path[match.end():].lstrip(".")
    return None, path


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

    from jonq.query_parser import parse_condition_string

    return generate_jq_condition(parse_condition_string(having, allow_alias_arithmetic=True))


def make_selector_from_path(path_with_arrays: str) -> str:
    return _array_source(parse_path(path_with_arrays), include_tail=False)


def _array_source(path: Path, *, include_tail: bool) -> str:
    pieces = []
    segments = []
    for element in path.elements:
        if element.type != PathType.ARRAY:
            segments.append(element)
            continue
        if element.value:
            segments.append(PathElement(PathType.FIELD, element.value))
        if segments:
            pieces.append(generate_jq_path(Path(segments)))
            segments = []
        pieces.append("arrays[]")
    if include_tail and segments:
        pieces.append(generate_jq_path(Path(segments)))
    return " | ".join(pieces)


def _split_array_context(path: str) -> tuple[Optional[str], str]:
    end = None
    for match in _PATH_ARRAYS.finditer(path):
        if match.group("array"):
            end = match.end()
    if end is None:
        return None, path
    return path[:end], path[end:].lstrip(".")


@dataclass(frozen=True)
class _ArrayProjection:
    scope: Path
    source_text: str
    column_count: int
    has_parent_columns: bool


def _array_scope_error(from_path: str | None, scope_text: str) -> ValueError:
    scope_text = scope_text.lstrip(".")
    if scope_text.startswith("[]"):
        sources = f"`from {scope_text}`"
    elif from_path:
        parent = from_path
        if resolve_from_path(parent) != parse_path(parent):
            parent += "[]"
        sources = f"`from {parent}.{scope_text}`"
    else:
        sources = f"`from {scope_text}` for an object or `from [].{scope_text}` for an array of parents"
    return ValueError(
        f"Select fields from one row source. Use {sources} and select paths relative to that source."
    )


def _implicit_field_array_context(fields, from_path: str | None) -> _ArrayProjection | None:
    scope = None
    source_text = ""
    column_count = 0
    has_parent_columns = False
    for tup in fields:
        ftype = tup[0]
        if ftype == "field":
            field_path = tup[1]
        elif ftype == "function":
            field_path = tup[2]
        else:
            continue
        context, _ = _split_array_context(field_path)
        if not context:
            has_parent_columns = True
            continue
        path = parse_path(context)
        if scope is None:
            scope = path
            source_text = context
        elif path != scope:
            raise _array_scope_error(from_path, source_text)
        column_count += 1
    if scope is not None:
        return _ArrayProjection(scope, source_text, column_count, has_parent_columns)
    return None


def _has_path_prefix(path: Path, prefix: Path) -> bool:
    return path.elements[:len(prefix.elements)] == prefix.elements


def _strip_array_context(path: str | Path, scope: Path) -> str | Path:
    parsed = parse_path(path)
    if _has_path_prefix(parsed, scope):
        return Path(parsed.elements[len(scope.elements):])
    return path


def _scope_array_filter(predicate: Predicate, scope: Path) -> tuple[Predicate, bool, bool]:
    uses_child = False
    uses_parent = False

    def rebase(path: str | Path) -> Path:
        nonlocal uses_child, uses_parent
        parsed = parse_path(path)
        if _has_path_prefix(parsed, scope):
            uses_child = True
            return Path(parsed.elements[len(scope.elements):])
        uses_parent = True
        return Path(parsed.elements, from_parent=True)

    def rebase_expression(expr: Expression) -> Expression:
        if expr.type == ExprType.FIELD:
            return replace(expr, value=rebase(expr.value))
        if not expr.args:
            return expr
        return replace(expr, args=[
            rebase_expression(arg) if isinstance(arg, Expression) else arg for arg in expr.args
        ])

    def visit(node: Predicate) -> Predicate:
        if isinstance(node, (AndCondition, OrCondition)):
            return replace(node, left=visit(node.left), right=visit(node.right))
        if isinstance(node, NotCondition):
            return replace(node, condition=visit(node.condition))
        if isinstance(node, (BetweenCondition, InCondition)):
            return replace(node, field=rebase(node.field))
        return replace(node, expr=rebase_expression(node.expr))

    rewritten = visit(predicate)
    return rewritten, uses_child, uses_parent


def _sort_filter(order_by: str, sort_direction: str, *, safe: bool = False) -> str:
    sort_expr = generate_jq_path(
        parse_path(order_by), context="root", null_check=safe
    )
    return f" | sort_by({sort_expr})" + (
        " | reverse" if sort_direction == "desc" else ""
    )


def _gen_field_selector(ftype: str, data: list, base_context: str) -> Optional[str]:
    if ftype == "field":
        field, alias = data
        path = generate_jq_path(parse_path(field), base_context)
        # A boxed value keeps false and null distinct from a filter that emitted nothing.
        return f"{json.dumps(alias)}: (({path} | [.]) // [null] | .[])"
    elif ftype == "aggregation":
        func, param, alias = data
        expr = Expression(ExprType.AGGREGATION, func, [param])
        context = "array" if base_context == "root" else base_context
        return f'"{alias}": {generate_jq_expression(expr, context)}'
    elif ftype == "expression":
        expr_txt, alias = data
        expr = parse_expression(expr_txt)
        context = "array" if base_context == "root" and contains_aggregate(expr) else base_context
        return f'"{alias}": {generate_jq_expression(expr, context)}'
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


def _aggregate_projection(field: tuple) -> bool:
    if field[0] in ("aggregation", "count_distinct"):
        return True
    return field[0] == "expression" and contains_aggregate(parse_expression(field[1]))


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
    all_aggregations = all(_aggregate_projection(field) for field in fields)
    root_array = [PathElement(PathType.ARRAY, "")]
    explicit_root_array = False
    if from_path:
        path = resolve_from_path(from_path)
        explicit_root_array = path.elements == root_array
        base_selector = _array_source(path, include_tail=True)
        base_context = "array"

    has_no_from_path = not from_path
    has_group_by = bool(group_by)
    group_by_has_arrays = any(_split_array_context(g)[0] for g in group_by) if group_by else False

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
    # Aggregate expressions keep their complete operand paths against the root rows.
    if not from_path and not group_by and all_aggregations and not any(
        field[0] == "expression" for field in fields
    ):
        first_param_with_array = next(
            (tup[2] for tup in fields if tup[0] == "aggregation" and _split_array_context(tup[2])[0]),
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

    if not group_by:
        projection = _implicit_field_array_context(fields, from_path)
    else:
        projection = None
    if projection is not None:
        field_array_context = projection.scope
        infer_child = (not from_path or explicit_root_array) and not projection.has_parent_columns
        uses_child = False
        if condition is not None and not isinstance(condition, str):
            scoped_condition, uses_child, use_parent = _scope_array_filter(condition, field_array_context)
        if not infer_child and (not from_path or projection.column_count > 1 or uses_child):
            raise _array_scope_error(from_path, projection.source_text)
        if infer_child:
            base_selector = _array_source(field_array_context, include_tail=False)
            base_context = "array"
            if uses_child:
                condition = scoped_condition
                if use_parent:
                    base_selector = f". as $jonq_parent | {base_selector}"
            elif condition:
                parent_condition = condition if isinstance(condition, str) else generate_jq_condition(condition)
                base_selector = f"select({parent_condition}) | {base_selector}"
                condition = None
            if field_array_context.elements[:1] != root_array:
                # Resolve relative nested paths from each root record.
                parents = "arrays[]" if from_path else '(if type=="array" then .[] else . end)'
                base_selector = f"{parents} | {base_selector}"
            if order_by:
                order_by = _strip_array_context(order_by, field_array_context)
            updated_fields = []
            for tup in fields:
                if tup[0] == "field":
                    _, path, alias = tup
                    updated_fields.append(
                        ("field", _strip_array_context(path, field_array_context), alias)
                    )
                elif tup[0] == "function":
                    _, func, param, alias = tup
                    updated_fields.append(
                        (
                            "function",
                            func,
                            _strip_array_context(param, field_array_context),
                            alias,
                        )
                    )
                elif tup[0] == "aggregation":
                    _, func, param, alias = tup
                    updated_fields.append(
                        ("aggregation", func, _strip_array_context(param, field_array_context), alias)
                    )
                else:
                    updated_fields.append(tup)
            fields = updated_fields

    if condition is not None and not isinstance(condition, str):
        condition = generate_jq_condition(condition, base_context)

    if all_aggregations and not group_by:
        base_data = base_selector or '(if type=="array" then .[] else . end)'
        if condition:
            base_data += f" | select({condition})"

        selection = [_gen_field_selector(kind, data, "aggregate") for kind, *data in fields]
        jq_filter = f"[ {base_data} ] | {{ {', '.join(selection)} }}"

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

        source = base_selector or ".[]"
        if condition:
            source = f"{source} | select({condition})"
        prefix = f"[ {source} ] | "

        jq_filter = f"{prefix}map(select(. != null)) | group_by({group_key}) | map({{ {', '.join(agg_sel)} }})"
        if having:
            jq_filter += f" | map(select({process_having_condition(having, fields)}))"
        if order_by:
            jq_filter += _sort_filter(order_by, sort_direction)
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
                jq_filter += _sort_filter(order_by, sort_direction)
            if limit:
                jq_filter += f" | .[0:{limit}]"

        elif (
            not any(ft[0] in ("field", "function", "count_distinct") for ft in fields)
            and not from_path
            and not group_by
            and any(ft[0] == "aggregation" for ft in fields)
        ):
            sel = []
            for ftype, *data in fields:
                s = _gen_field_selector(ftype, data, base_context)
                if s:
                    sel.append(s)
            map_filter = f"{{ {', '.join(sel)} }}"
            jq_filter = f"[{map_filter}]"
        else:
            sel = []
            for ftype, *data in fields:
                s = _gen_field_selector(ftype, data, base_context)
                if s:
                    sel.append(s)
            map_filter = f"{{ {', '.join(sel)} }}"
            sort_path = parse_path(order_by).elements if order_by else []
            sort_projection = (
                len(sort_path) == 1
                and sort_path[0].type == PathType.FIELD
                and any(field[-1] == sort_path[0].value for field in fields)
            )
            source_sort = ""
            if order_by and not sort_projection:
                if distinct:
                    raise ValueError("Sort field must be selected when using distinct")
                source_sort = _sort_filter(order_by, sort_direction, safe=True)
            row_filter = f"select({condition}) | " if condition else ""
            if from_path or base_selector:
                if source_sort:
                    filter_source = f" | select({condition})" if condition else ""
                    jq_filter = f"[ {base_selector}{filter_source} ]{source_sort} | map({map_filter})"
                else:
                    jq_filter = f"[ {base_selector} | {row_filter}{map_filter} ]"
            else:
                array_projection = f". | map({row_filter}{map_filter})"
                if source_sort:
                    filter_array = f" | map(select({condition}))" if condition else ""
                    array_projection = f".{filter_array}{source_sort} | map({map_filter})"
                scalar_projection = ""
                if any(ft[0] in ("field", "function", "count_distinct") for ft in fields):
                    scalar = '[{"value":.}]'
                    if condition:
                        scalar = f"if {condition} then {scalar} else [] end"
                    scalar_projection = f'elif type=="number" or type=="string" then {scalar} '
                jq_filter = (
                    f'if type=="array" then {array_projection} '
                    f'elif type=="object" then [{row_filter}{map_filter}] '
                    f"{scalar_projection}else [] end"
                )
            if distinct:
                jq_filter += " | unique"
            if sort_projection:
                jq_filter += _sort_filter(order_by, sort_direction)
            if limit:
                jq_filter += f" | .[0:{limit}]"
    logging.info(f"Generated jq filter: {jq_filter}")
    return jq_filter
