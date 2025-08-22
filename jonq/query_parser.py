import re
from jonq.tokenizer import tokenize
from jonq.ast import *
from jonq.generator import generate_jq_condition

_NUM_RE = re.compile(r'^[+-]?((\d+(\.\d*)?)|(\.\d+))([eE][+-]?\d+)?$')

def tokenize_query(query):
    if not isinstance(query, str):
        raise ValueError("Query must be a string")
    tokens = tokenize(query)
    if not is_balanced(tokens):
        raise ValueError("Unbalanced parentheses in query")
    return tokens

def is_balanced(tokens):
    depth = 0
    for token in tokens:
        if token == '(':
            depth += 1
        elif token == ')':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0

def extract_value_from_quotes(value):
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    elif value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value

def _normalize_quotes(s: str) -> str:
    return re.sub(r"'([^']*)'", r'"\1"', s)

def _normalize_equals(s: str) -> str:
    return re.sub(r'(?<![!<>=])\s=\s(?![=])', ' == ', s)

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

def _split_top_level(s: str, needle: str):
    n = len(needle)
    depth = 0
    in_sq = in_dq = False
    i = 0
    while i <= len(s) - n:
        ch = s[i]
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "(" and not in_sq and not in_dq:
            depth += 1
        elif ch == ")" and not in_sq and not in_dq:
            depth -= 1
        if depth == 0 and not in_sq and not in_dq and s[i:i+n].lower() == needle:
            return s[:i], s[i+n:]
        i += 1
    return None, None

def _find_top_level_comparison_span(s: str):
    patterns = [
        (" == ", "=="),
        (" != ", "!="),
        (" >= ", ">="),
        (" <= ", "<="),
        (" > ",  ">"),
        (" < ",  "<"),
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

def _expr_from_string(expr_str: str) -> Expression:
    expr_str = expr_str.strip()
    if expr_str.startswith('"') and expr_str.endswith('"'):
        return Expression(ExprType.LITERAL, expr_str)
    if _NUM_RE.match(expr_str):
        return Expression(ExprType.LITERAL, expr_str)
    return Expression(ExprType.FIELD, expr_str)

def parse_condition_string(cond_str: str) -> Condition:
    s = _normalize_equals(_normalize_quotes(cond_str.strip()))
    s = _strip_outer_parens(s)

    left, right = _split_top_level(s, " or ")
    if left is not None:
        return OrCondition(parse_condition_string(left), parse_condition_string(right))

    m = re.match(r"^(.*?)\s+between\s+(.+?)\s+and\s+(.+?)\s*$", s, flags=re.IGNORECASE)
    if m:
        field, low, high = m.groups()
        return BetweenCondition(field.strip(), low.strip(), high.strip())

    left, right = _split_top_level(s, " and ")
    if left is not None:
        return AndCondition(parse_condition_string(left), parse_condition_string(right))

    m = re.match(r"^(.*?)\s+between\s+(\S+)\s+and\s+(\S+)\s*$", s, flags=re.IGNORECASE)
    if m:
        field, low, high = m.groups()
        return BetweenCondition(field.strip(), low.strip(), high.strip())

    m = re.match(r"^(.*?)\s+contains\s+(.+)$", s, flags=re.IGNORECASE)
    if m:
        field, value = m.groups()
        field_expr = _expr_from_string(field.strip())
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            val_expr = Expression(ExprType.LITERAL, _normalize_quotes(value))
        else:
            val_expr = Expression(ExprType.LITERAL, f'"{value}"')
        return Condition(Expression(ExprType.BINARY_CONDITION, "contains", [field_expr, val_expr]))

    i0, i1, op = _find_top_level_comparison_span(s)
    if i0 != -1:
        left = s[:i0].strip()
        right = s[i1:].strip()
        return Condition(Expression(ExprType.BINARY_CONDITION, op, [_expr_from_string(left), _expr_from_string(right)]))

    return Condition(_expr_from_string(s))

def parse_condition_for_from(tokens):
    if not tokens:
        return None
    condition_str = " ".join(tokens)
    cond = parse_condition_string(condition_str)
    return generate_jq_condition(cond, "array")

def parse_condition(tokens):
    if not tokens:
        return None
    condition_str = " ".join(tokens)
    
    cond = parse_condition_string(condition_str)
    return generate_jq_condition(cond, "root")

def parse_query(tokens):
    if not tokens or tokens[0].lower() != 'select':
        raise ValueError("Query must start with 'select'")
    i = 1
    fields = []
    expecting_field = True
    while i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', 'having', 'from']:
        if tokens[i] == ',':
            if not expecting_field:
                expecting_field = True
                i += 1
            else:
                raise ValueError(f"Unexpected comma at position {i}")
            continue
        if expecting_field:
            if tokens[i] == '*':
                fields.append(('field', '*', '*'))
                i += 1
                expecting_field = False
                continue
            if i + 1 < len(tokens) and tokens[i + 1] == '(':
                func = tokens[i]
                depth = 0
                end_idx = i
                while end_idx < len(tokens):
                    tok = tokens[end_idx]
                    if tok == '(':
                        depth += 1
                    elif tok == ')':
                        depth -= 1
                        if depth == 0:
                            break
                    end_idx += 1
                if depth != 0:
                    raise ValueError("Unbalanced parentheses in field list")
                inner_expr = " ".join(tokens[i + 2: end_idx])
                i = end_idx + 1
                alias = None
                if i < len(tokens) and tokens[i] == 'as':
                    i += 1
                    if i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', 'having', ',', 'from']:
                        alias = tokens[i]
                        i += 1
                    else:
                        raise ValueError("Expected alias after 'as'")
                    is_plain_path = re.fullmatch(r'[\w\.\[\]]+', inner_expr)
                    is_star = inner_expr.strip() == '*'
                    if is_plain_path or is_star:
                        alias = alias or f"{func}_{inner_expr.replace('.', '_').replace('[', '_').replace(']', '').replace('*', 'star')}"
                        fields.append(('aggregation', func, inner_expr, alias))
                    else:
                        alias = alias or f"expr_{len(fields) + 1}"
                        fields.append(('expression', f"{func} ( {inner_expr} )", alias))
                expecting_field = False
                continue
            else:
                depth = 0
                field_tokens = []
                while i < len(tokens):
                    token = tokens[i]
                    if token == '(':
                        depth += 1
                    elif token == ')':
                        depth -= 1
                    elif depth == 0 and token in [',', 'as'] or token.lower() in ['if', 'sort', 'group', 'having', 'from']:
                        break
                    field_tokens.append(token)
                    i += 1
                if not field_tokens:
                    raise ValueError("Expected field name")
                if len(field_tokens) > 1 and all(t.isidentifier() for t in field_tokens):
                    raise ValueError(f"Unexpected token {field_tokens[1]!r} after field name")
                alias = None
                if i < len(tokens) and tokens[i] == 'as':
                    i += 1
                    if i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', 'having', ',', 'from']:
                        alias = tokens[i]
                        i += 1
                    else:
                        raise ValueError("Expected alias after 'as'")
                if len(field_tokens) == 1:
                    field_token = field_tokens[0]
                    if (field_token.startswith('"') and field_token.endswith('"')) or (field_token.startswith("'") and field_token.endswith("'")):
                        field_token = field_token[1:-1]
                    field_path = field_token
                    alias = alias or field_path.split('.')[-1].replace(' ', '_')
                    fields.append(('field', field_path, alias))
                else:
                    expression = ' '.join(field_tokens)
                    alias = alias or f"expr_{len(fields) + 1}"
                    fields.append(('expression', expression, alias))
            expecting_field = False
        else:
            break
    from_path = None
    if i < len(tokens) and tokens[i].lower() == 'from':
        i += 1
        if i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', 'having']:
            from_path = tokens[i]
            i += 1
        else:
            raise ValueError("Expected path after 'from'")
    condition = None
    if i < len(tokens) and tokens[i].lower() == 'if':
        i += 1
        condition_tokens = []
        while i < len(tokens) and tokens[i].lower() not in ['sort', 'group', 'having']:
            condition_tokens.append(tokens[i])
            i += 1
        condition = parse_condition_for_from(condition_tokens) if from_path else parse_condition(condition_tokens)
    group_by = None
    if i < len(tokens) and tokens[i].lower() == 'group':
        i += 1
        if i < len(tokens) and tokens[i].lower() == 'by':
            i += 1
            group_by_fields = []
            expecting_field = True
            while i < len(tokens) and tokens[i].lower() not in ['sort', 'having', 'from']:
                if tokens[i] == ',':
                    i += 1
                    expecting_field = True
                    continue
                if expecting_field:
                    field_token = tokens[i]
                    if (field_token.startswith('"') and field_token.endswith('"')) or (field_token.startswith("'") and field_token.endswith("'")):
                        field_token = field_token[1:-1]
                    group_by_fields.append(field_token)
                    expecting_field = False
                i += 1
            if not group_by_fields:
                raise ValueError("Expected field(s) after 'group by'")
            group_by = group_by_fields
        else:
            raise ValueError("Expected 'by' after 'group'")
    having = None
    if i < len(tokens) and tokens[i].lower() == 'having':
        if not group_by:
            raise ValueError("HAVING clause can only be used with GROUP BY")
        i += 1
        having_tokens = []
        while i < len(tokens) and tokens[i].lower() not in ['sort', 'from']:
            having_tokens.append(tokens[i])
            i += 1
        having = " ".join(having_tokens)
    if i < len(tokens) and tokens[i].lower() == 'from':
        i += 1
        if i < len(tokens) and tokens[i].lower() not in ['sort']:
            from_path = tokens[i]
            i += 1
        else:
            raise ValueError("Expected path after 'from'")
    order_by = None
    sort_direction = 'asc'
    limit = None
    if i < len(tokens) and tokens[i].lower() == 'sort':
        i += 1
        if i < len(tokens):
            order_by = tokens[i]
            i += 1
            if i < len(tokens) and tokens[i].lower() in ['desc', 'asc']:
                sort_direction = tokens[i].lower()
                i += 1
            if i < len(tokens) and tokens[i].isdigit():
                limit = tokens[i]
                i += 1
            if i < len(tokens) and tokens[i].lower() == 'from':
                i += 1
                if i < len(tokens):
                    from_path = tokens[i]
                    i += 1
                else:
                    raise ValueError("Expected path after 'from'")
    if from_path is None and i < len(tokens) and tokens[i].lower() == 'from':
        i += 1
        if i < len(tokens):
            from_path = tokens[i]
            i += 1
        else:
            raise ValueError("Expected path after 'from'")
    return fields, condition, group_by, having, order_by, sort_direction, limit, from_path
