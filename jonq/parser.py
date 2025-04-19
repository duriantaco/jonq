import re
from jonq.ast import *

def parse_path(path_str):
    if not path_str or path_str == '*':
        return Path([])
        
    elements = []
    parts = re.split(r'\.(?![^\[]*\])', path_str.lstrip('.'))
    
    for part in parts:
        if '[]' in part:
            base, *rest = part.split('[]', 1)
            elements.append(PathElement(PathType.ARRAY, base))
            if rest:
                elements.extend(parse_path(rest[0]).elements)
        elif '[' in part and ']' in part:
            idx_matches = list(re.finditer(r'\[(\d+)\]', part))
            if idx_matches:
                base = part[:idx_matches[0].start()]
                if base:
                    elements.append(PathElement(PathType.FIELD, base))
                
                for i, match in enumerate(idx_matches):
                    idx = match.group(1)
                    elements.append(PathElement(PathType.ARRAY_INDEX, idx))
                    
                    if i < len(idx_matches) - 1:
                        field = part[match.end():idx_matches[i+1].start()]
                        if field and field.startswith('.'):
                            field = field[1:]
                        if field:
                            elements.append(PathElement(PathType.FIELD, field))
                
                if idx_matches[-1].end() < len(part):
                    field = part[idx_matches[-1].end():]
                    if field and field.startswith('.'):
                        field = field[1:]
                    if field:
                        elements.append(PathElement(PathType.FIELD, field))
            else:
                elements.append(PathElement(PathType.FIELD, part))
        else:
            elements.append(PathElement(PathType.FIELD, part))
            
    return Path(elements)

def parse_expression(expr_str):
    expr_str = expr_str.strip()

    depth = 0
    for i, ch in enumerate(expr_str):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            for op in ['+', '-', '*', '/']:
                pat = f" {op} "
                if expr_str.startswith(pat, i):
                    left = expr_str[:i].rstrip()
                    right = expr_str[i + len(pat):].lstrip()
                    return Expression(
                        ExprType.OPERATION,
                        op,
                        [parse_expression(left), parse_expression(right)]
                    )

    agg_match = re.match(r'(\w+)\s*\(\s*([^)]+)\s*\)', expr_str)
    if agg_match:
        func, arg = agg_match.group(1), agg_match.group(2)
        if func in ["sum", "avg", "min", "max", "count"]:
            return Expression(ExprType.AGGREGATION, func, [arg.strip()])

    if expr_str.isdigit() or (expr_str.startswith('"') and expr_str.endswith('"')):
        return Expression(ExprType.LITERAL, expr_str)

    return Expression(ExprType.FIELD, expr_str)

def parse_condition(cond_str):
    if " and " in cond_str:
        left, right = cond_str.split(" and ", 1)
        return AndCondition(parse_condition(left), parse_condition(right))
    
    if " or " in cond_str:
        left, right = cond_str.split(" or ", 1)
        return OrCondition(parse_condition(left), parse_condition(right))
    
    between_match = re.match(r'(.*?)\s+between\s+(\S+)\s+and\s+(\S+)', cond_str, re.IGNORECASE)
    if between_match:
        field, low, high = between_match.groups()
        return BetweenCondition(field.strip(), low.strip(), high.strip())
    
    for op in ["==", "!=", ">=", "<=", ">", "<"]:
        if f" {op} " in cond_str:
            left, right = cond_str.split(f" {op} ", 1)
            left_expr = parse_expression(left)
            right_expr = parse_expression(right)
            return Condition(Expression(
                ExprType.BINARY_CONDITION,
                op,
                [left_expr, right_expr]
            ))
    
    contains_match = re.match(r'(.*?)\s+contains\s+(\S+.*)', cond_str, re.IGNORECASE)
    if contains_match:
        field, value = contains_match.groups()
        field_expr = parse_expression(field.strip())
        value = value.strip()
        if value.startswith("'") and value.endswith("'"):
            value_expr = Expression(ExprType.LITERAL, value)
        elif value.startswith('"') and value.endswith('"'):
            value_expr = Expression(ExprType.LITERAL, value)
        else:
            value_expr = Expression(ExprType.LITERAL, f'"{value}"')
        
        return Condition(Expression(
            ExprType.BINARY_CONDITION,
            "contains",
            [field_expr, value_expr]
        ))
    
    return Condition(parse_expression(cond_str))

def parse_condition_tokens(tokens):
    if not tokens:
        return None
        
    condition_str = " ".join(tokens)
    condition_str = re.sub(r"'([^']*)'", r'"\1"', condition_str)
    condition_str = condition_str.replace(" = = ", " == ").replace("==", " == ")
    condition_str = condition_str.replace(" = ", " == ")
    
    if "between" in condition_str.lower():
        between_parts = re.split(r'\s+between\s+', condition_str, flags=re.IGNORECASE)
        if len(between_parts) == 2 and " and " in between_parts[1]:
            field = between_parts[0].strip()
            range_parts = between_parts[1].split(" and ", 1)
            if len(range_parts) == 2:
                low, high = range_parts[0].strip(), range_parts[1].strip()
                return BetweenCondition(field, low, high)
    
    if "contains" in condition_str.lower():
        contains_parts = re.split(r'\s+contains\s+', condition_str, flags=re.IGNORECASE)
        if len(contains_parts) == 2:
            field = contains_parts[0].strip()
            value = contains_parts[1].strip()
            field_expr = parse_expression(field)
            value_expr = Expression(ExprType.LITERAL, value if value.startswith('"') or value.startswith("'") else f'"{value}"')
            return Condition(Expression(
                ExprType.BINARY_CONDITION,
                "contains",
                [field_expr, value_expr]
            ))
    
    return parse_condition(condition_str)