import re
from jonq.tokenizer import tokenize
from jonq.ast import *
from jonq.generator import generate_jq_condition
from jonq.parser import parse_condition as ast_parse_condition

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

def parse_condition_for_from(tokens):
    if not tokens:
        return None
    
    tokens_lower = [t.lower() for t in tokens]
    
    if "contains" in tokens_lower:
        try:
            contains_idx = tokens_lower.index("contains")
            field_tokens = tokens[:contains_idx]
            value_tokens = tokens[contains_idx + 1:]
            
            if not field_tokens or not value_tokens:
                raise ValueError("Invalid CONTAINS condition: missing field or value")
            
            field = " ".join(field_tokens).strip()
            value = " ".join(value_tokens).strip()
            value = extract_value_from_quotes(value)
            
            return f"(.{field} | tostring | contains(\"{value}\"))"
        except ValueError as e:
            raise ValueError(f"Error parsing CONTAINS condition: {str(e)}")
    
    if "between" in tokens_lower:
        try:
            between_idx = tokens_lower.index("between")
            and_idx = tokens_lower.index("and", between_idx)
            
            field = " ".join(tokens[:between_idx]).strip()
            low = " ".join(tokens[between_idx + 1:and_idx]).strip()
            high = " ".join(tokens[and_idx + 1:]).strip()
            
            return f"(.{field} >= {low} and .{field} <= {high})"
        except ValueError:
            raise ValueError("Invalid BETWEEN condition: missing 'and' or malformed range")
    
    condition_str = " ".join(tokens)
    condition_str = re.sub(r"'([^']*)'", r'"\1"', condition_str)
    condition_str = condition_str.replace(" = = ", " == ").replace("==", " == ")
    condition = ast_parse_condition(condition_str)
    return generate_jq_condition(condition, "array").replace('?', '')

def parse_condition(tokens):
    if not tokens:
        return None
    
    condition_str = " ".join(tokens)
    condition_str = re.sub(r"'([^']*)'", r'"\1"', condition_str)
    condition_str = condition_str.replace(" = = ", " == ").replace("==", " == ")
    condition = ast_parse_condition(condition_str)
    return generate_jq_condition(condition, "root")

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
                
            field_tokens = []
            start = i
            
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

                inner_expr = " ".join(tokens[i + 2 : end_idx])
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
                    is_star       = inner_expr.strip() == '*'

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
                    if (field_token.startswith('"') and field_token.endswith('"')) or \
                    (field_token.startswith("'") and field_token.endswith("'")):
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