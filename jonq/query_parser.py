from __future__ import annotations
import json
import re
from typing import Optional
from jonq.tokenizer import tokenize
from jonq.ast import (
    AndCondition,
    BetweenCondition,
    Condition,
    Expression,
    ExprType,
    InCondition,
    NotCondition,
    OrCondition,
)
from jonq.generator import generate_jq_condition
from jonq.parser import _QUOTED_KEY, contains_aggregate, decode_quoted_key, parse_expression, parse_path
from jonq.utils import _split_top_level

_NUM_RE = re.compile(r"^[+-]?((\d+(\.\d*)?)|(\.\d+))([eE][+-]?\d+)?$")
_FIELD_TOKEN = re.compile(rf"(?:{_QUOTED_KEY.pattern}|[\w.\[\]-])+")


def tokenize_query(query: str) -> list[str]:
    if not isinstance(query, str):
        raise ValueError("Query must be a string")
    tokens = tokenize(query)
    if not is_balanced(tokens):
        raise ValueError("Unbalanced parentheses in query")
    return tokens


def is_balanced(tokens: list[str]) -> bool:
    depth = 0
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _normalize_quotes(s: str) -> str:
    return _QUOTED_KEY.sub(
        lambda match: json.dumps(decode_quoted_key(match.group()))
        if match.group().startswith("'") else match.group(),
        s,
    )


def _normalize_equals(s: str) -> str:
    return re.sub(
        _QUOTED_KEY.pattern + r"|(?<![!<>=\S])(?:=\s+=|=)(?!\S)",
        lambda match: match.group() if match.group().startswith(('"', "'")) else "==",
        s,
    )


def _strip_outer_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        ok = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    ok = False
                    break
        if ok:
            s = s[1:-1].strip()
        else:
            break
    return s


def _find_top_level_comparison_span(s: str):
    patterns = [
        (" == ", "=="),
        (" != ", "!="),
        (" >= ", ">="),
        (" <= ", "<="),
        (" > ", ">"),
        (" < ", "<"),
    ]
    depth = 0
    in_sq = in_dq = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "(" and not in_sq and not in_dq:
            depth += 1
        elif ch == ")" and not in_sq and not in_dq:
            depth -= 1
        if depth == 0 and not in_sq and not in_dq:
            for pat, op in patterns:
                L = len(pat)
                if s.startswith(pat, i):
                    return i, i + L, op
        i += 1
    return -1, -1, ""


def _expr_from_string(expr_str: str, *, field_position: bool = False) -> Expression:
    expr_str = expr_str.strip()
    if not expr_str:
        raise ValueError("Expected value in condition")
    if _QUOTED_KEY.fullmatch(expr_str):
        return Expression(ExprType.FIELD if field_position else ExprType.LITERAL, expr_str)
    if expr_str.lower() in {"true", "false", "null"}:
        return Expression(ExprType.LITERAL, expr_str.lower())
    if _NUM_RE.match(expr_str):
        return Expression(ExprType.LITERAL, expr_str)
    return Expression(ExprType.FIELD, expr_str)


def parse_condition_string(cond_str: str, *, allow_alias_arithmetic: bool = False):
    s = _normalize_equals(_normalize_quotes(cond_str.strip()))
    s = _strip_outer_parens(s)

    def parse_child(text: str):
        return parse_condition_string(text, allow_alias_arithmetic=allow_alias_arithmetic)

    def parse_operand(text: str, *, field_position: bool = False) -> Expression:
        expr = _expr_from_string(text, field_position=field_position)
        if expr.type == ExprType.FIELD:
            if allow_alias_arithmetic and not _QUOTED_KEY.fullmatch(expr.value):
                expr = parse_expression(expr.value)
                if contains_aggregate(expr):
                    raise ValueError("HAVING must refer to selected aggregate aliases")
            elif not _FIELD_TOKEN.fullmatch(expr.value):
                raise ValueError(f"Expected a field path or literal, got {expr.value!r}")
        return expr

    left, right = _split_top_level(s, " or ")
    if left is not None:
        return OrCondition(parse_child(left), parse_child(right))

    stripped = s.strip()

    m = re.match(r"^(.+?)\s+is\s+not\s+null\s*$", stripped, flags=re.IGNORECASE)
    if m:
        field = m.group(1).strip()
        return Condition(
            Expression(ExprType.BINARY_CONDITION, "!=", [
                parse_operand(field, field_position=True),
                Expression(ExprType.LITERAL, "null"),
            ])
        )
    m = re.match(r"^(.+?)\s+is\s+null\s*$", stripped, flags=re.IGNORECASE)
    if m:
        field = m.group(1).strip()
        return Condition(
            Expression(ExprType.BINARY_CONDITION, "==", [
                parse_operand(field, field_position=True),
                Expression(ExprType.LITERAL, "null"),
            ])
        )

    if stripped.lower().startswith("not "):
        inner = stripped[4:].strip()
        return NotCondition(parse_child(inner))

    m = re.match(r"^(.*?)\s+between\s+(.+?)\s+and\s+(.+?)\s*$", s, flags=re.IGNORECASE)
    if m:
        field, low, high = m.groups()
        parse_operand(field, field_position=True)
        return BetweenCondition(field.strip(), low.strip(), high.strip())

    left, right = _split_top_level(s, " and ")
    if left is not None:
        return AndCondition(parse_child(left), parse_child(right))

    m = re.match(r"^(.*?)\s+between\s+(\S+)\s+and\s+(\S+)\s*$", s, flags=re.IGNORECASE)
    if m:
        field, low, high = m.groups()
        parse_operand(field, field_position=True)
        return BetweenCondition(field.strip(), low.strip(), high.strip())

    m = re.match(r"^(.+?)\s+in\s*\((.+)\)\s*$", s, flags=re.IGNORECASE)
    if m:
        field = m.group(1).strip()
        parse_operand(field, field_position=True)
        values_str = m.group(2)
        values = []
        for v in values_str.split(","):
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (
                v.startswith("'") and v.endswith("'")
            ):
                v = f'"{v[1:-1]}"'
            values.append(v)
        return InCondition(field, values)

    m = re.match(r"^(.+?)\s+like\s+(.+)$", s, flags=re.IGNORECASE)
    if m:
        field = m.group(1).strip()
        pattern = m.group(2).strip()
        if (pattern.startswith('"') and pattern.endswith('"')) or (
            pattern.startswith("'") and pattern.endswith("'")
        ):
            pattern = pattern[1:-1]
        return Condition(
            Expression(
                ExprType.BINARY_CONDITION,
                "like",
                [
                    parse_operand(field, field_position=True),
                    Expression(ExprType.LITERAL, f'"{pattern}"'),
                ],
            )
        )

    m = re.match(r"^(.*?)\s+contains\s+(.+)$", s, flags=re.IGNORECASE)
    if m:
        field, value = m.groups()
        field_expr = parse_operand(field.strip(), field_position=True)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            val_expr = Expression(ExprType.LITERAL, _normalize_quotes(value))
        else:
            val_expr = Expression(ExprType.LITERAL, f'"{value}"')
        return Condition(
            Expression(ExprType.BINARY_CONDITION, "contains", [field_expr, val_expr])
        )

    comparison = f" {s} "
    i0, i1, op = _find_top_level_comparison_span(comparison)
    if i0 != -1:
        left = comparison[:i0].strip()
        right = comparison[i1:].strip()
        return Condition(
            Expression(
                ExprType.BINARY_CONDITION,
                op,
                [parse_operand(left, field_position=True), parse_operand(right)],
            )
        )

    return Condition(parse_operand(s))


def parse_condition_for_from(tokens: list[str]) -> Optional[str]:
    if not tokens:
        return None
    condition_str = " ".join(tokens)
    cond = parse_condition_string(condition_str)
    return generate_jq_condition(cond, "array")


def parse_condition(tokens: list[str]) -> Optional[str]:
    if not tokens:
        return None
    condition_str = " ".join(tokens)

    cond = parse_condition_string(condition_str)
    return generate_jq_condition(cond, "root")


_SCALAR_FUNCTIONS = {
    "upper", "lower", "length", "round", "abs", "ceil", "floor",
    "int", "float", "str", "string", "to_number", "to_string",
    "keys", "values", "type", "trim", "reverse", "sort", "unique",
    "flatten", "not_null", "to_entries", "from_entries",
    "todate", "fromdate", "date", "timestamp",
    "ltrim", "rtrim", "tojson", "fromjson",
}
_MULTI_ARG_FUNCTIONS = {"coalesce", "if_null"}
_AGGREGATE_FUNCTIONS = {"count", "sum", "avg", "min", "max"}
_ARITHMETIC_OPS = {"+", "-", "*", "/", "%", "^", "||"}
_FILTER_CLAUSES = {"if", "where"}
_SELECT_CLAUSES = _FILTER_CLAUSES | {"sort", "group", "having", "from", "limit"}
_ALIAS_STOP_TOKENS = _SELECT_CLAUSES | {","}


def _quoted_field(token: str) -> tuple[str, str]:
    if not _QUOTED_KEY.fullmatch(token):
        if _QUOTED_KEY.search(token):
            elements = parse_path(token).elements
            return token, elements[-1].value.replace(" ", "_")
        return token, token.split(".")[-1].replace(" ", "_")
    name = decode_quoted_key(token)
    # Keep quote boundaries where they change the meaning of path syntax.
    if name and name == name.strip() and name != "*" and not name.startswith("'") and not any(
        character in name for character in '.[]"'
    ):
        token = name
    return token, name.replace(" ", "_")


def _join_quoted_path_tokens(tokens: list[str]) -> list[str]:
    merged: list[str] = []
    for token in tokens:
        if merged:
            previous = merged[-1]
            if (previous.endswith(".") and _QUOTED_KEY.fullmatch(token)) or (
                previous.endswith(('"', "'")) and token.startswith((".", "["))
            ):
                merged[-1] += token
                continue
        merged.append(token)
    return merged


def parse_query(tokens: list[str]) -> tuple:
    fields, predicate, *clauses = parse_query_structure(tokens)
    from_path = clauses[-2]
    condition = (
        generate_jq_condition(predicate, "array" if from_path else "root")
        if predicate is not None
        else None
    )
    return fields, condition, *clauses


def parse_query_structure(tokens: list[str]) -> tuple:
    """Parse a query while retaining the WHERE predicate for scope resolution."""
    tokens = _join_quoted_path_tokens(tokens)
    if not tokens or tokens[0].lower() != "select":
        raise ValueError("Query must start with 'select'")
    i = 1
    distinct = False
    if i < len(tokens) and tokens[i].lower() == "distinct":
        distinct = True
        i += 1
    fields = []
    expecting_field = True
    while i < len(tokens) and tokens[i].lower() not in _SELECT_CLAUSES:
        if tokens[i] == ",":
            if not expecting_field:
                expecting_field = True
                i += 1
            else:
                raise ValueError(f"Unexpected comma at position {i}")
            continue
        if expecting_field:
            if tokens[i] == "*":
                fields.append(("field", "*", "*"))
                i += 1
                expecting_field = False
                continue
            if tokens[i].lower() == "case":
                case_tokens = []
                i += 1
                while i < len(tokens) and tokens[i].lower() != "end":
                    case_tokens.append(tokens[i])
                    i += 1
                if i < len(tokens) and tokens[i].lower() == "end":
                    i += 1
                case_expr = " ".join(case_tokens)
                alias = None
                if i < len(tokens) and tokens[i] == "as":
                    i += 1
                    if i < len(tokens) and tokens[i].lower() not in _ALIAS_STOP_TOKENS:
                        alias = tokens[i]
                        i += 1
                    else:
                        raise ValueError("Expected alias after 'as'")
                alias = alias or f"case_{len(fields) + 1}"
                fields.append(("expression", f"case {case_expr} end", alias))
                expecting_field = False
                continue
            if i + 1 < len(tokens) and tokens[i + 1] == "(":
                start_idx = i
                func = tokens[i]
                depth = 0
                end_idx = i
                while end_idx < len(tokens):
                    tok = tokens[end_idx]
                    if tok == "(":
                        depth += 1
                    elif tok == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    end_idx += 1
                if depth != 0:
                    raise ValueError("Unbalanced parentheses in field list")
                inner_tokens = tokens[i + 2 : end_idx]
                inner_expr = " ".join(inner_tokens)
                i = end_idx + 1
                if i < len(tokens) and tokens[i] in _ARITHMETIC_OPS:
                    expr_tokens = tokens[start_idx:i]
                    depth = 0
                    while i < len(tokens):
                        token = tokens[i]
                        if token == "(":
                            depth += 1
                        elif token == ")":
                            depth -= 1
                        if depth == 0 and (
                            token == ","
                            or token.lower()
                            in (_SELECT_CLAUSES | {"as"})
                        ):
                            break
                        expr_tokens.append(token)
                        i += 1
                    alias = None
                    if i < len(tokens) and tokens[i] == "as":
                        i += 1
                        if i < len(tokens) and tokens[i].lower() not in _ALIAS_STOP_TOKENS:
                            alias = tokens[i]
                            i += 1
                        else:
                            raise ValueError("Expected alias after 'as'")
                    expression = " ".join(expr_tokens)
                    alias = alias or f"expr_{len(fields) + 1}"
                    fields.append(("expression", expression, alias))
                    expecting_field = False
                    continue
                alias = None
                if i < len(tokens) and tokens[i] == "as":
                    i += 1
                    if i < len(tokens) and tokens[i].lower() not in _ALIAS_STOP_TOKENS:
                        alias = tokens[i]
                        i += 1
                    else:
                        raise ValueError("Expected alias after 'as'")
                func_lower = func.lower()
                if (
                    func_lower == "count"
                    and inner_tokens
                    and inner_tokens[0].lower() == "distinct"
                ):
                    cd_field = " ".join(inner_tokens[1:])
                    alias = alias or f"count_distinct_{cd_field.replace('.', '_')}"
                    fields.append(("count_distinct", cd_field, alias))
                elif func_lower in _MULTI_ARG_FUNCTIONS:
                    alias = alias or f"{func_lower}_{len(fields) + 1}"
                    fields.append(("expression", f"{func_lower}({inner_expr})", alias))
                elif func_lower in _SCALAR_FUNCTIONS:
                    alias = alias or f"{func_lower}_{inner_expr.replace('.', '_')}"
                    fields.append(("function", func_lower, inner_expr, alias))
                else:
                    is_plain_path = re.fullmatch(r"[\w\.\[\]]+", inner_expr)
                    is_star = inner_expr.strip() == "*"
                    if func_lower not in _AGGREGATE_FUNCTIONS:
                        raise ValueError(f"Unknown function '{func}'")
                    if is_plain_path or is_star:
                        alias = (
                            alias
                            or f"{func}_{inner_expr.replace('.', '_').replace('[', '_').replace(']', '').replace('*', 'star')}"
                        )
                        fields.append(("aggregation", func_lower, inner_expr, alias))
                    else:
                        alias = alias or f"expr_{len(fields) + 1}"
                        fields.append(("expression", f"{func} ( {inner_expr} )", alias))
                expecting_field = False
                continue
            else:
                depth = 0
                field_tokens = []
                while i < len(tokens):
                    token = tokens[i]
                    if token == "(":
                        depth += 1
                    elif token == ")":
                        depth -= 1
                    elif depth == 0 and (
                        token in [",", "as"]
                        or token.lower()
                        in _SELECT_CLAUSES
                    ):
                        break
                    field_tokens.append(token)
                    i += 1
                if not field_tokens:
                    raise ValueError("Expected field name")
                if len(field_tokens) > 1 and all(
                    t not in _ARITHMETIC_OPS and _FIELD_TOKEN.fullmatch(t) for t in field_tokens
                ):
                    raise ValueError(f"Expected a comma before {field_tokens[1]!r}")
                alias = None
                if i < len(tokens) and tokens[i] == "as":
                    i += 1
                    if i < len(tokens) and tokens[i].lower() not in _ALIAS_STOP_TOKENS:
                        alias = tokens[i]
                        i += 1
                    else:
                        raise ValueError("Expected alias after 'as'")
                if len(field_tokens) == 1:
                    field_path, default_alias = _quoted_field(field_tokens[0])
                    fields.append(("field", field_path, alias or default_alias))
                else:
                    expression = " ".join(field_tokens)
                    alias = alias or f"expr_{len(fields) + 1}"
                    fields.append(("expression", expression, alias))
            expecting_field = False
        else:
            break
    if not fields:
        raise ValueError("Expected field list after 'select'")
    if expecting_field:
        raise ValueError("Expected field name after comma")
    from_path = None
    if i < len(tokens) and tokens[i].lower() == "from":
        i += 1
        if i < len(tokens) and tokens[i].lower() not in (
            _FILTER_CLAUSES | {"sort", "group", "having", "limit"}
        ):
            from_path = tokens[i]
            i += 1
        else:
            raise ValueError("Expected path after 'from'")
    condition = None
    if i < len(tokens) and tokens[i].lower() in _FILTER_CLAUSES:
        i += 1
        condition_tokens = []
        while i < len(tokens) and tokens[i].lower() not in [
            "sort",
            "group",
            "having",
            "limit",
        ]:
            condition_tokens.append(tokens[i])
            i += 1
        if not condition_tokens:
            raise ValueError("Expected a condition after 'where' or 'if'")
        condition = parse_condition_string(" ".join(condition_tokens))
    group_by = None
    if i < len(tokens) and tokens[i].lower() == "group":
        i += 1
        if i < len(tokens) and tokens[i].lower() == "by":
            i += 1
            group_by_fields = []
            expecting_field = True
            while i < len(tokens) and tokens[i].lower() not in [
                "sort",
                "having",
                "from",
                "limit",
            ]:
                if tokens[i] == ",":
                    if expecting_field:
                        raise ValueError("Expected field before comma in 'group by'")
                    i += 1
                    expecting_field = True
                    continue
                if expecting_field:
                    field_token, _ = _quoted_field(tokens[i])
                    group_by_fields.append(field_token)
                    expecting_field = False
                else:
                    raise ValueError("Expected comma between 'group by' fields")
                i += 1
            if expecting_field:
                raise ValueError("Expected field(s) after 'group by'")
            group_by = group_by_fields
        else:
            raise ValueError("Expected 'by' after 'group'")
    having = None
    if i < len(tokens) and tokens[i].lower() == "having":
        if not group_by:
            raise ValueError("HAVING clause can only be used with GROUP BY")
        i += 1
        having_tokens = []
        while i < len(tokens) and tokens[i].lower() not in ["sort", "from", "limit"]:
            having_tokens.append(tokens[i])
            i += 1
        if not having_tokens:
            raise ValueError("Expected a condition after 'having'")
        having = " ".join(having_tokens)
    if i < len(tokens) and tokens[i].lower() == "from":
        i += 1
        if i < len(tokens) and tokens[i].lower() not in ["sort", "limit"]:
            from_path = tokens[i]
            i += 1
        else:
            raise ValueError("Expected path after 'from'")
    order_by = None
    sort_direction = "asc"
    limit = None
    if i < len(tokens) and tokens[i].lower() == "sort":
        i += 1
        if i == len(tokens) or tokens[i].lower() in _SELECT_CLAUSES:
            raise ValueError("Expected field after 'sort'")
        if i < len(tokens):
            order_by = tokens[i]
            i += 1
            if i < len(tokens) and tokens[i].lower() in ["desc", "asc"]:
                sort_direction = tokens[i].lower()
                i += 1
            if i < len(tokens) and tokens[i].isdigit():
                limit = tokens[i]
                i += 1
            if i < len(tokens) and tokens[i].lower() == "from":
                i += 1
                if i < len(tokens):
                    from_path = tokens[i]
                    i += 1
                else:
                    raise ValueError("Expected path after 'from'")
    if from_path is None and i < len(tokens) and tokens[i].lower() == "from":
        i += 1
        if i < len(tokens):
            from_path = tokens[i]
            i += 1
        else:
            raise ValueError("Expected path after 'from'")
    # Standalone LIMIT
    if i < len(tokens) and tokens[i].lower() == "limit":
        i += 1
        if i < len(tokens) and tokens[i].isdigit():
            limit = tokens[i]
            i += 1
        else:
            raise ValueError("Expected number after 'limit'")
    if i < len(tokens):
        raise ValueError(f"Unexpected token {tokens[i]!r} at position {i}")
    return (
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
