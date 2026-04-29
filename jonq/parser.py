import re
from jonq.ast import (
    AndCondition,
    BetweenCondition,
    Condition,
    Expression,
    ExprType,
    OrCondition,
    Path,
    PathElement,
    PathType,
)
from jonq.utils import _split_top_level


def parse_path(path_str: str) -> Path:
    if not path_str or path_str == "*":
        return Path([])

    elements = []
    cleaned_path = path_str.lstrip(".")
    parts = re.split(r"\.(?![^\[]*\])", cleaned_path)

    for part in parts:
        if "[]" in part:
            base, *rest = part.split("[]", 1)
            elements.append(PathElement(PathType.ARRAY, base))
            if rest:
                remaining_path = rest[0]
                parsed_remaining = parse_path(remaining_path)
                elements.extend(parsed_remaining.elements)

        elif "[" in part and "]" in part:
            idx_matches = list(re.finditer(r"\[(\d+)\]", part))
            if idx_matches:
                base = part[: idx_matches[0].start()]
                if base:
                    elements.append(PathElement(PathType.FIELD, base))

                for i, match in enumerate(idx_matches):
                    idx = match.group(1)
                    elements.append(PathElement(PathType.ARRAY_INDEX, idx))

                    if i < len(idx_matches) - 1:
                        field = part[match.end() : idx_matches[i + 1].start()]
                        if field and field.startswith("."):
                            field = field[1:]
                        if field:
                            elements.append(PathElement(PathType.FIELD, field))

                if idx_matches[-1].end() < len(part):
                    field = part[idx_matches[-1].end() :]
                    if field and field.startswith("."):
                        field = field[1:]
                    if field:
                        elements.append(PathElement(PathType.FIELD, field))
            else:
                elements.append(PathElement(PathType.FIELD, part))
        else:
            elements.append(PathElement(PathType.FIELD, part))

    return Path(elements)


def _split_args(s: str) -> list[str]:
    args = []
    depth = 0
    current = []
    in_sq = in_dq = False
    for ch in s:
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == '(' and not in_sq and not in_dq:
            depth += 1
        elif ch == ')' and not in_sq and not in_dq:
            depth -= 1
        elif ch == ',' and depth == 0 and not in_sq and not in_dq:
            args.append(''.join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        args.append(''.join(current).strip())
    return args


def _parse_case_expression(expr_str: str) -> Expression:
    """Parse CASE WHEN cond THEN val [WHEN ...] [ELSE val] END into a CASE expression."""
    body = expr_str[4:].strip()  # strip leading 'case'
    if body.lower().endswith("end"):
        body = body[:-3].strip()

    whens = []
    else_val = None

    remaining = body
    while remaining:
        remaining = remaining.strip()
        lower = remaining.lower()
        if lower.startswith("when "):
            remaining = remaining[5:]
            then_pos = _find_keyword(remaining, "then")
            if then_pos == -1:
                break
            cond_str = remaining[:then_pos].strip()
            remaining = remaining[then_pos + 4:].strip()
            next_when = _find_keyword(remaining, "when")
            next_else = _find_keyword(remaining, "else")
            end_pos = len(remaining)
            if next_when != -1:
                end_pos = min(end_pos, next_when)
            if next_else != -1:
                end_pos = min(end_pos, next_else)
            val_str = remaining[:end_pos].strip()
            whens.append((cond_str, val_str))
            remaining = remaining[end_pos:]
        elif lower.startswith("else "):
            else_val = remaining[5:].strip()
            break
        else:
            break

    return Expression(ExprType.CASE, else_val, whens)


def _find_keyword(s: str, keyword: str) -> int:
    pattern = re.compile(r'\b' + keyword + r'\b', re.IGNORECASE)
    in_sq = in_dq = False
    for m in pattern.finditer(s):
        pos = m.start()
        in_sq = in_dq = False
        for ch in s[:pos]:
            if ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not in_sq:
                in_dq = not in_dq
        if not in_sq and not in_dq:
            return pos
    return -1


def _strip_outer_expr_parens(expr_str: str) -> str:
    expr_str = expr_str.strip()
    while expr_str.startswith("(") and expr_str.endswith(")"):
        depth = 0
        in_sq = in_dq = False
        wraps = True
        for i, ch in enumerate(expr_str):
            if ch == "'" and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not in_sq:
                in_dq = not in_dq
            elif ch == "(" and not in_sq and not in_dq:
                depth += 1
            elif ch == ")" and not in_sq and not in_dq:
                depth -= 1
                if depth == 0 and i != len(expr_str) - 1:
                    wraps = False
                    break
        if not wraps:
            break
        expr_str = expr_str[1:-1].strip()
    return expr_str


def _find_top_level_operator(expr_str: str, operators: list[str]):
    depth = 0
    in_sq = in_dq = False
    i = len(expr_str) - 1
    while i >= 0:
        ch = expr_str[i]
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == ")" and not in_sq and not in_dq:
            depth += 1
        elif ch == "(" and not in_sq and not in_dq:
            depth -= 1
        elif depth == 0 and not in_sq and not in_dq:
            for op in operators:
                if op == "||":
                    for pat in (" || ", "||"):
                        start = i - len(pat) + 1
                        if start >= 0 and expr_str[start : i + 1] == pat:
                            return start, op
                else:
                    pat = f" {op} "
                    start = i - len(pat) + 1
                    if start >= 0 and expr_str[start : i + 1] == pat:
                        return start, op
        i -= 1
    return None, None


def parse_expression(expr_str: str) -> Expression:
    expr_str = _strip_outer_expr_parens(expr_str)

    if expr_str.lower().startswith("case "):
        return _parse_case_expression(expr_str)

    for operators in (["||", "+", "-"], ["*", "/", "%"]):
        op_index, op = _find_top_level_operator(expr_str, operators)
        if op_index is not None:
            pat_len = len(op)
            if op == "||":
                if expr_str.startswith(" || ", op_index):
                    pat_len = 4
                elif expr_str.startswith("||", op_index):
                    pat_len = 2
            else:
                pat_len = len(f" {op} ")
            left = expr_str[:op_index].rstrip()
            right = expr_str[op_index + pat_len :].lstrip()
            return Expression(
                ExprType.OPERATION,
                "+" if op == "||" else op,
                [parse_expression(left), parse_expression(right)],
            )

    agg_match = re.match(r"(\w+)\s*\(", expr_str)
    if agg_match:
        func = agg_match.group(1)
        start = agg_match.end() - 1
        depth = 0
        end = start
        for j in range(start, len(expr_str)):
            if expr_str[j] == '(':
                depth += 1
            elif expr_str[j] == ')':
                depth -= 1
                if depth == 0:
                    end = j
                    break
        arg = expr_str[start + 1:end].strip()

        if func == "coalesce":
            args = _split_args(arg)
            return Expression(ExprType.FUNCTION, "coalesce", [
                parse_expression(a) for a in args
            ])
        if func in ["sum", "avg", "min", "max", "count"]:
            return Expression(ExprType.AGGREGATION, func, [arg.strip()])
        if func in [
            "upper", "lower", "length", "round", "abs", "ceil", "floor",
            "int", "float", "str", "string", "to_number", "to_string",
            "keys", "values", "type", "trim", "reverse", "sort", "unique",
            "flatten", "not_null", "to_entries", "from_entries",
            "todate", "fromdate", "date", "timestamp",
            "ltrim", "rtrim", "tojson", "fromjson",
        ]:
            return Expression(
                ExprType.FUNCTION, func, [Expression(ExprType.FIELD, arg.strip())]
            )

    _NUM_RE = re.compile(
        r"""
        ^[+-]?(
            (\d+(\.\d*)?)|(\.\d+)
        )([eE][+-]?\d+)?$
    """,
        re.VERBOSE,
    )

    if _NUM_RE.match(expr_str) or (expr_str.startswith('"') and expr_str.endswith('"')):
        return Expression(ExprType.LITERAL, expr_str)

    # Single-quoted strings → convert to double-quoted literal
    if expr_str.startswith("'") and expr_str.endswith("'") and len(expr_str) >= 2:
        inner = expr_str[1:-1]
        return Expression(ExprType.LITERAL, f'"{inner}"')

    return Expression(ExprType.FIELD, expr_str)


def parse_condition(cond_str):
    left, right = _split_top_level(cond_str, " or ")
    if left is not None:
        return OrCondition(parse_condition(left), parse_condition(right))

    left, right = _split_top_level(cond_str, " and ")
    if left is not None:
        return AndCondition(parse_condition(left), parse_condition(right))

    between_match = re.match(
        r"(.*?)\s+between\s+(\S+)\s+and\s+(\S+)", cond_str, re.IGNORECASE
    )
    if between_match:
        field, low, high = between_match.groups()
        return BetweenCondition(field.strip(), low.strip(), high.strip())

    for op in ["==", "!=", ">=", "<=", ">", "<"]:
        if f" {op} " in cond_str:
            left, right = cond_str.split(f" {op} ", 1)
            left_expr = parse_expression(left)
            right_expr = parse_expression(right)
            return Condition(
                Expression(ExprType.BINARY_CONDITION, op, [left_expr, right_expr])
            )

    contains_match = re.match(r"(.*?)\s+contains\s+(\S+.*)", cond_str, re.IGNORECASE)
    if contains_match:
        field, value = contains_match.groups()
        field_expr = parse_expression(field.strip())
        value = value.strip()
        if (value.startswith("'") and value.endswith("'")) or (
            value.startswith('"') and value.endswith('"')
        ):
            value_expr = Expression(ExprType.LITERAL, value)
        else:
            value_expr = Expression(ExprType.LITERAL, f'"{value}"')
        return Condition(
            Expression(ExprType.BINARY_CONDITION, "contains", [field_expr, value_expr])
        )

    return Condition(parse_expression(cond_str))


def parse_condition_tokens(tokens):
    if not tokens:
        return None

    condition_str = " ".join(tokens)
    condition_str = re.sub(r"'([^']*)'", r'"\1"', condition_str)
    condition_str = condition_str.replace(" = = ", " == ").replace("==", " == ")
    condition_str = condition_str.replace(" = ", " == ")

    if "between" in condition_str.lower():
        between_parts = re.split(r"\s+between\s+", condition_str, flags=re.IGNORECASE)
        if len(between_parts) == 2 and " and " in between_parts[1]:
            field = between_parts[0].strip()
            range_parts = between_parts[1].split(" and ", 1)
            if len(range_parts) == 2:
                low, high = range_parts[0].strip(), range_parts[1].strip()
                return BetweenCondition(field, low, high)

    if "contains" in condition_str.lower():
        contains_parts = re.split(r"\s+contains\s+", condition_str, flags=re.IGNORECASE)
        if len(contains_parts) == 2:
            field = contains_parts[0].strip()
            value = contains_parts[1].strip()
            field_expr = parse_expression(field)
            value_expr = Expression(
                ExprType.LITERAL,
                value
                if value.startswith('"') or value.startswith("'")
                else f'"{value}"',
            )
            return Condition(
                Expression(
                    ExprType.BINARY_CONDITION, "contains", [field_expr, value_expr]
                )
            )

    return parse_condition(condition_str)
