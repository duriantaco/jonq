import re
import json
from jonq.jq_filter import build_jq_path
from jonq.tokenizer import tokenize

def tokenize_query(query):
    if not isinstance(query, str):
        raise ValueError("Query must be a string")
    tokens = tokenize(query)
    if not is_balanced(tokens):
        raise ValueError("Unbalanced parentheses in query")
    return tokens

def parse_query(tokens):
    if not tokens:
        raise ValueError("Empty query. Please provide a valid query (e.g., 'select *').")
    if tokens[0].lower() != 'select':
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
            field_tokens = []
            start = i
            if i+3 < len(tokens) and tokens[i+1] == '(' and tokens[i+3] == ')':
                func = tokens[i]
                param = tokens[i+2]
                i += 4
                field_tokens = [func, '(', param, ')']
                if i < len(tokens) and tokens[i] in ['+', '-', '*', '/']:
                    while i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', 'having', ',', 'as', 'from']:
                        field_tokens.append(tokens[i])
                        i += 1
                alias = None
                if i < len(tokens) and tokens[i] == 'as':
                    i += 1
                    if i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', 'having', ',', 'from']:
                        alias = tokens[i]
                        i += 1
                    else:
                        raise ValueError("Expected alias after 'as'")
                if len(field_tokens) > 4:
                    alias = alias or f"expr_{len(fields) + 1}"
                    fields.append(('expression', ' '.join(field_tokens), alias))
                else:
                    alias = alias or f"{func}_{param.replace('.', '_').replace('[', '_').replace(']', '')}"
                    fields.append(('aggregation', func, param, alias))
            else:
                depth = 0
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
                if len(field_tokens) > 1:
                    for j in range(len(field_tokens) - 1):
                        if (re.match(r'[a-zA-Z_][a-zA-Z0-9_.]*$', field_tokens[j]) or field_tokens[j].isdigit()) and \
                           (re.match(r'[a-zA-Z_][a-zA-Z0-9_.]*$', field_tokens[j+1]) or field_tokens[j+1].isdigit()):
                            raise ValueError(f"Unexpected tokens: {' '.join(tokens[start:])}")
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
                    if (field_token.startswith('"') and field_token.endswith('"')) or \
                       (field_token.startswith("'") and field_token.endswith("'")):
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
        condition = parse_condition(condition_tokens)
    group_by = None
    if i < len(tokens) and tokens[i].lower() == 'group':
        i += 1
        if i < len(tokens) and tokens[i].lower() == 'by':
            i += 1
            group_by_fields = []
            while i < len(tokens) and tokens[i].lower() not in ['sort', 'having']:
                if tokens[i] == ',':
                    i += 1
                    continue
                field_token = tokens[i]
                if (field_token.startswith('"') and field_token.endswith('"')) or \
                   (field_token.startswith("'") and field_token.endswith("'")):
                    field_token = field_token[1:-1]
                group_by_fields.append(field_token)
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
        while i < len(tokens) and tokens[i].lower() not in ['sort']:
            having_tokens.append(tokens[i])
            i += 1
        having = parse_condition(having_tokens)
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
        else:
            raise ValueError("Expected field name after 'sort'")
    if i < len(tokens):
        raise ValueError(f"Unexpected tokens: {' '.join(tokens[i:])}")
    return fields, condition, group_by, having, order_by, sort_direction, limit, from_path

def parse_condition(tokens):
    if not tokens:
        return None
    ast, pos = parse_or_expression(tokens, 0)
    if pos < len(tokens):
        raise ValueError(f"Unexpected tokens in condition: {' '.join(tokens[pos:])}")
    return transform_ast(ast)

def parse_or_expression(tokens, pos):
    expr, pos = parse_and_expression(tokens, pos)
    while pos < len(tokens) and tokens[pos].lower() == 'or':
        op = tokens[pos]
        pos += 1
        right, pos = parse_and_expression(tokens, pos)
        expr = (op.lower(), expr, right)
    return expr, pos

def parse_and_expression(tokens, pos):
    expr, pos = parse_comparison(tokens, pos)
    while pos < len(tokens) and tokens[pos].lower() == 'and':
        op = tokens[pos]
        pos += 1
        right, pos = parse_comparison(tokens, pos)
        expr = (op.lower(), expr, right)
    return expr, pos

def parse_comparison(tokens, pos):
    if pos >= len(tokens):
        raise ValueError("Unexpected end of tokens")
    if tokens[pos] == '(':
        pos += 1
        expr, pos = parse_or_expression(tokens, pos)
        if pos < len(tokens) and tokens[pos] == ')':
            pos += 1
            return expr, pos
        else:
            raise ValueError("Unbalanced parentheses")
    else:
        if pos + 2 < len(tokens):
            field = tokens[pos]
            op = tokens[pos + 1]
            value = tokens[pos + 2]
            if op in ['=', '==', '!=', '>', '<', '>=', '<=']:
                return {'type': 'comparison', 'field': field, 'op': op, 'value': value}, pos + 3
        raise ValueError(f"Invalid comparison at position {pos}")

def transform_ast(ast):
    if isinstance(ast, dict) and ast.get('type') == 'comparison':
        field = transform_field(ast['field'])
        op = transform_operator(ast['op'])
        value = transform_value(ast['value'])
        return f"{field} {op} {value}"
    elif isinstance(ast, tuple):
        op, left, right = ast
        left_cond = transform_ast(left)
        right_cond = transform_ast(right)
        return f"({left_cond} {op} {right_cond})"
    else:
        raise ValueError(f"Invalid AST node: {ast}")

def transform_field(token):
    if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
        content = token[1:-1]
        return f'."{content}"?'
    elif re.match(r'[a-zA-Z_][a-zA-Z0-9_.]*(\[\d+\])?(\.[a-zA-Z0-9_]+(\[\d+\])?)*', token):
        return build_jq_path(token)
    else:
        raise ValueError(f"Invalid field name: {token}")

def transform_value(token):
    if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
        content = token[1:-1]
        return json.dumps(content)
    elif token.isdigit():
        return token
    else:
        raise ValueError(f"Invalid value: {token}")

def transform_operator(op):
    if op in ['=', '==']:
        return '=='
    return op

def find_lowest_precedence_operator(tokens):
    depth = 0
    or_idx = -1
    and_idx = -1
    for i, token in enumerate(tokens):
        if token == '(':
            depth += 1
        elif token == ')':
            depth -= 1
        elif depth == 0 and token.lower() == 'or':
            or_idx = i
        elif depth == 0 and token.lower() == 'and' and or_idx == -1:
            and_idx = i
    return or_idx if or_idx != -1 else and_idx

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

def parse_query_compat(tokens):
    fields, condition, group_by, having, order_by, sort_direction, limit, from_path = parse_query(tokens)
    return fields, condition, order_by, sort_direction, limit