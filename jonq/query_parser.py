import re
import json
from jonq.jq_filter import build_jq_path

## I think might be easier to do a tokenizer library in the next update
def tokenize(query):
    """
    This function breaks down a query string into individual tokens by recognizing various elements including:
    - Function calls with wildcard parameter: func(*)
    - Function calls with specific parameters: func(param)
    - Arithmetic operators: +, -, *, /
    - Quoted strings (both single and double quotes)
    - Other non-whitespace characters
    - Commas and parentheses

    Args:
        query (str): The input query string to be tokenized.

    Returns:
        list: A list of tokens extracted from the query string.
    """
    pattern = r'(\w+\s*\(\s*\*\s*\))|(\w+\s*\(\s*[\w\.\[\]]+\s*\))|\s+\-\s+|\s+\+\s+|\s+\*\s+|\s+\/\s+|\'[^\']*\'|"[^"]*"|[^\s,()]+|,|\(|\)'
    tokens = []
    for match in re.finditer(pattern, query):
        token = match.group(0).strip()
        if token in ['+', '-', '*', '/'] or re.match(r'\s+[\+\-\*\/]\s+', token):
            tokens.append(token.strip())
        elif re.match(r'^\w+\s*\(\s*\*\s*\)$', token):
            func = re.match(r'^(\w+)\s*\(\s*\*\s*\)$', token).group(1)
            tokens.append(func)
            tokens.append('(')
            tokens.append('*')
            tokens.append(')')
        elif re.match(r'^\w+\s*\(\s*[\w\.\[\]]+\s*\)$', token):
            func = re.match(r'^(\w+)\s*\(\s*', token).group(1)
            param = re.search(r'\(\s*([\w\.\[\]]+)\s*\)$', token).group(1)
            tokens.append(func)
            tokens.append('(')
            tokens.append(param)
            tokens.append(')')
        else:
            tokens.append(token)
    return tokens

def parse_query(tokens):
    """
    This function parses a SQL-like query string into fields, conditions, grouping, and sorting components.
    Parameters
    ----------
    tokens : list
        List of string tokens that make up the query
    Returns
    -------
    tuple
        A 6-tuple containing:
        - fields : list
            List of tuples describing the selected fields/expressions:
            ('field', field_path, alias) for simple fields
            ('expression', expression_string, alias) for expressions
            ('aggregation', function, parameter, alias) for aggregation functions
        - condition : dict or None
            Parsed condition tree if IF clause present, None otherwise
        - group_by : list or None
            List of fields to group by if GROUP BY clause present, None otherwise
        - order_by : str or None
            Field to sort by if SORT clause present, None otherwise
        - sort_direction : str
            Sort direction ('asc' or 'desc'), defaults to 'asc'
        - limit : str or None
            Number of results to limit to if specified after SORT, None otherwise
    Raises
    ------
    ValueError
        If the query syntax is invalid or missing required components
    """
    if not tokens:
        raise ValueError("Empty query. Please provide a valid query (e.g., 'select *').")
    if tokens[0].lower() != 'select':
        raise ValueError("Query must start with 'select'")
    i = 1
    fields = []
    
    expecting_field = True
    while i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group']:
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
                    while i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', ',', 'as']:
                        field_tokens.append(tokens[i])
                        i += 1
                        
                alias = None
                if i < len(tokens) and tokens[i] == 'as':
                    i += 1
                    if i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', ',']:
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
                    elif depth == 0 and token in [',', 'as'] or token.lower() in ['if', 'sort', 'group']:
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
                    if i < len(tokens) and tokens[i].lower() not in ['if', 'sort', 'group', ',']:
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
    
    condition = None
    if i < len(tokens) and tokens[i].lower() == 'if':
        i += 1
        condition_tokens = []
        while i < len(tokens) and tokens[i].lower() not in ['sort', 'group']:
            condition_tokens.append(tokens[i])
            i += 1
        condition = parse_condition(condition_tokens)
    
    group_by = None
    if i < len(tokens) and tokens[i].lower() == 'group':
        i += 1
        if i < len(tokens) and tokens[i].lower() == 'by':
            i += 1
            group_by_fields = []
            while i < len(tokens) and tokens[i].lower() not in ['sort']:
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
    
    return fields, condition, group_by, order_by, sort_direction, limit

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
        left = tokens[pos]
        pos += 1
        if pos < len(tokens) and tokens[pos] in ['=', '!=', '>', '<', '>=', '<=']:
            op = tokens[pos]
            pos += 1
            if pos < len(tokens):
                right = tokens[pos]
                pos += 1
                return ('comparison', left, op, right), pos
            else:
                raise ValueError("Expected value after operator")
        else:
            raise ValueError("Expected operator after field")

def transform_ast(ast):
    """
    This function processes AST nodes representing logical operations ('and', 'or') and
    comparisons, converting them into properly formatted query strings.

    Returns:
        str: A formatted query string representing the AST node.

    Raises:
        ValueError: If the AST node format is invalid or if a right-hand value in a
                   comparison is neither a valid string literal nor a number.
    """
    if isinstance(ast, tuple):
        if ast[0] in ['and', 'or']:
            left = transform_ast(ast[1])
            right = transform_ast(ast[2])
            return f"({left} {ast[0]} {right})"
        elif ast[0] == 'comparison':
            left_token = ast[1]
            left = transform_field(left_token)
            op = transform_operator(ast[2])
            right_token = ast[3]
            if (right_token.startswith('"') and right_token.endswith('"')) or (right_token.startswith("'") and right_token.endswith("'")):
                content = right_token[1:-1]
                if (left_token.startswith('"') and left_token.endswith('"')) or (left_token.startswith("'") and left_token.endswith("'")):
                    right = f"'{content}'"
                else:
                    right = json.dumps(content)
            elif right_token.isdigit():
                right = right_token
            else:
                raise ValueError(f"Invalid value: {right_token}")
            return f"{left} {op} {right}"
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
    return '==' if op == '=' else op

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
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    return fields, condition, order_by, sort_direction, limit