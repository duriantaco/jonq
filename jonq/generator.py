import logging
import re
from jonq.ast import *
from jonq.parser import parse_path, parse_expression

logging.basicConfig(level=logging.INFO)

def generate_jq_path(path, context="root", null_check=True):
    if not path.elements:
        return "."

    result = ""
    for i, element in enumerate(path.elements):
        if element.type == PathType.FIELD:
            seg = f".{element.value}"
            if i == 0:
                result += seg
            else:
                result += seg
        elif element.type == PathType.ARRAY:
            seg = f".{element.value}[]?"
            if i == 0:
                result += seg
            else:
                result += seg
        elif element.type == PathType.ARRAY_INDEX:
            result += f"[{element.value}]?"

    if null_check:
        parts = result.split(".")
        for i in range(1, len(parts)):
            if "[]?" not in parts[i] and not re.search(r'\[\d+\]\?$', parts[i]):
                parts[i] = parts[i] + "?"
        result = ".".join(parts)

    return result

def generate_jq_expression(expr, context="root"):
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
        
        if context == "group" and '[]' in arg:
            if func == "count":
                return f"(map({arg_jq}) | length)"
            elif func == "sum":
                return f"(map({arg_jq} | select(type==\"number\")) | add // 0)"
            elif func == "avg":
                return (
                    f"(map({arg_jq} | select(type==\"number\")) "
                    f"| if length>0 then (add/length) else null end)"
                )
            elif func == "max":
                return f"(map({arg_jq} | select(type==\"number\")) | max?)"
            elif func == "min":
                return f"(map({arg_jq} | select(type==\"number\")) | min?)"

        if '[]' in arg:
            if func == "count":
                return f"([{arg_jq}] | length)"
            elif func == "sum":
                return f"([{arg_jq}] | flatten | map(select(type == \"number\")) | add // 0)"
            elif func == "avg":
                return f"([{arg_jq}] | flatten | map(select(type == \"number\")) | if length > 0 then (add / length) else null end)"
            elif func == "max":
                return f"([{arg_jq}] | flatten | map(select(type == \"number\")) | if length > 0 then max else null end)"
            elif func == "min":
                return f"([{arg_jq}] | flatten | map(select(type == \"number\")) | if length > 0 then min else null end)"
            else:
                return f"([{arg_jq}] | length)"

        else:
            if context == "group":
                if func == "count":
                    return f"(map({arg_jq} | if type == \"array\" then length else 1 end) | add // 0)"
                elif func == "sum":
                    return f"(map({arg_jq} | if type == \"array\" then (map(select(type == \"number\")) | add // []) else select(type == \"number\") end) | flatten | add // 0)"
                elif func == "avg":
                    return f"(map({arg_jq} | if type == \"array\" then (map(select(type == \"number\")) | add // []) else select(type == \"number\") end) | flatten | if length > 0 then (add / length) else null end)"
                elif func == "max":
                    return f"(map({arg_jq} | if type == \"array\" then (map(select(type == \"number\")) | add // []) else select(type == \"number\") end) | flatten | if length > 0 then max else null end)"
                elif func == "min":
                    return f"(map({arg_jq} | if type == \"array\" then (map(select(type == \"number\")) | add // []) else select(type == \"number\") end) | flatten | if length > 0 then min else null end)"
            elif context == "array":
                if func == "count":
                    return f"(.{arg} | if type == \"array\" then length else 1 end)"
                elif func == "sum":
                    return f"(.{arg} | if type == \"array\" then (map(select(type == \"number\")) | add // 0) else (if type == \"number\" then . else 0 end) end)"
                elif func == "avg":
                    return f"(.{arg} | if type == \"array\" and length > 0 then (map(select(type == \"number\")) | add / length) else (if type == \"number\" then . else null end) end)"
                elif func == "max":
                    return f"(.{arg} | if type == \"array\" and length > 0 then (map(select(type == \"number\")) | max) else (if type == \"number\" then . else null end) end)"
                elif func == "min":
                    return f"(.{arg} | if type == \"array\" and length > 0 then (map(select(type == \"number\")) | min) else (if type == \"number\" then . else null end) end)"
            else:
                if func == "count":
                    return f"length"
                elif func == "sum":
                    return f"([.[] | {arg_jq} | select(type == \"number\")] | add // 0)"
                elif func == "avg":
                    return f"([.[] | {arg_jq} | select(type == \"number\")] | if length > 0 then (add / length) else null end)"
                elif func == "max":
                    return f"([.[] | {arg_jq} | select(type == \"number\")] | if length > 0 then max else null end)"
                elif func == "min":
                    return f"([.[] | {arg_jq} | select(type == \"number\")] | if length > 0 then min else null end)"
    elif expr.type == ExprType.LITERAL:
        return str(expr.value)
    elif expr.type == ExprType.OPERATION:
        op = expr.value
        left = generate_jq_expression(expr.args[0], context)
        right = generate_jq_expression(expr.args[1], context)
        return f"(({left}) {op} ({right}))"
    elif expr.type == ExprType.BINARY_CONDITION:
        op = expr.value
        left = generate_jq_expression(expr.args[0], context)
        right = generate_jq_expression(expr.args[1], context)
        
        if op == "contains":
            return f"({left} != null and ({left} | tostring) | contains({right}))"
        else:
            return f"{left} {op} {right}"
    
    return str(expr.value)

def generate_jq_condition(cond, context="root"):
    if isinstance(cond, AndCondition):
        left = generate_jq_condition(cond.left, context)
        right = generate_jq_condition(cond.right, context)
        return f"({left} and {right})"
    elif isinstance(cond, OrCondition):
        left = generate_jq_condition(cond.left, context)
        right = generate_jq_condition(cond.right, context)
        return f"({left} or {right})"
    elif isinstance(cond, BetweenCondition):
        path = parse_path(cond.field)
        path_jq = generate_jq_path(path, context)
        return f"({path_jq} != null and {path_jq} >= {cond.low} and {path_jq} <= {cond.high})"
    elif isinstance(cond, Condition):
        return generate_jq_expression(cond.expr, context)
    
    return ""

def split_base_array(path: str):
    if '[]' not in path:
        return None, path
    before, after = path.split('[]', 1)
    before = before.rstrip('.')
    after  = after.lstrip('.')
    return before, after

def strip_prefix(path: str, prefix: str) -> str:
    needle = f'{prefix}[]'
    return path[len(needle):].lstrip('.') if path.startswith(needle) else path

def format_field_path(field):
    path = parse_path(field)
    return generate_jq_path(path)

def build_jq_path(field_path):
    path = parse_path(field_path)
    return generate_jq_path(path)

def transform_nested_array_path(field_path):
    path = parse_path(field_path)
    return generate_jq_path(path, context="array")

def escape_string(s):
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        content = s[1:-1]
        escaped = content.replace('"', '\\"')
        return f'"{escaped}"'
    return s

def process_having_condition(having):
    if not having:
        return ""
    
    having = re.sub(r'\bavg_age\b', '.avg_age', having)
    having = re.sub(r'\bcount\b', '.count', having)
    having = re.sub(r'\bavg_monthly\b', '.avg_monthly', having)
    having = re.sub(r'\btotal_revenue\b', '.total_revenue', having)
    having = re.sub(r'\bavg_price\b', '.avg_price', having)
    having = re.sub(r'\btotal_price\b', '.total_price', having)
    having = re.sub(r'\bmin_age\b', '.min_age', having)
    having = re.sub(r'\bmax_age\b', '.max_age', having)
    having = re.sub(r'\bavg_profit\b', '.avg_profit', having)
    having = re.sub(r'\btotal_spent\b', '.total_spent', having)
    having = re.sub(r'\btotal_orders\b', '.total_orders', having)
    having = re.sub(r'\bprice_order_ratio\b', '.price_order_ratio', having)
    having = re.sub(r'\buser_count\b', '.user_count', having)
    having = re.sub(r'\bversion_count\b', '.version_count', having)
    having = re.sub(r'\bcustomer_count\b', '.customer_count', having)
    having = re.sub(r'\bavg_yearly\b', '.avg_yearly', having)
    having = re.sub(r'\bprice_range\b', '.price_range', having)
    having = re.sub(r'\bavg_monthly_price\b', '.avg_monthly_price', having)
    
    for op in [" > ", " < ", " >= ", " <= ", " == "]:
        if op in having:
            parts = having.split(op, 1)
            left = parts[0].strip()
            right = parts[1].strip()
            
            if not left.startswith(".") and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', left):
                left = f".{left}"
                
            return f"{left}{op}{right}"
    
    if ' and ' in having:
        parts = having.split(' and ')
        conditions = []
        for part in parts:
            part = part.strip()
            for op in [' > ', ' < ', ' >= ', ' <= ', ' == ']:
                if op in part:
                    left, right = part.split(op, 1)
                    left = left.strip()
                    right = right.strip()
                    
                    if not left.startswith(".") and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', left):
                        left = f".{left}"
                        
                    conditions.append(f"{left}{op}{right}")
                    break
                    
        return ' and '.join(conditions)
    
    return having

def make_selector_from_path(path_with_arrays: str) -> str:
    bits   = path_with_arrays.split('[]')
    pieces = []
    running = bits[0].lstrip('.')
    while True:
        pieces.append(f'.{running.strip(".")}[]')
        if len(bits) == 1 or not bits[1]:
            break
        nxt = bits[1]
        if nxt.startswith('.'):
            nxt = nxt[1:]
        if '[]' in nxt:
            running = nxt.split('[]',1)[0]
            bits[1] = nxt.split('[]',1)[1]
        else:
            break
    return ' | '.join(pieces)

def generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path=None):
    base_context = "root"
    base_selector = ""

    if from_path:
        if from_path == '[]':
            base_selector = '.[]'
            base_context = "array"
        elif from_path.startswith('[]'):
            nested_path = from_path[2:]
            if nested_path.startswith('.'):
                nested_path = nested_path[1:]
            base_selector = f'.[] | .{nested_path}[]'
            base_context = "array"
        elif '[]' in from_path:
            parts = from_path.split('[]', 1)
            if parts[0]:
                if parts[0].startswith('.'):
                    parts[0] = parts[0][1:]
                base = f'.{parts[0]}'
            else:
                base = '.'
                
            if len(parts) > 1 and parts[1]:
                rest = parts[1]
                if rest.startswith('.'):
                    rest = rest[1:]
                base_selector = f'{base}[] | .{rest}'
            else:
                base_selector = f'{base}[]'
            base_context = "array"
        else:
            base_selector = f'.{from_path}'
            base_context = "object"
    
    if not from_path and group_by:
        implicit_base, inner = split_base_array(group_by[0])
        if implicit_base:
            base_selector = make_selector_from_path(group_by[0])
            base_context  = "array"

            group_by = [split_base_array(g)[1] for g in group_by]

            new_fields = []
            for tup in fields:
                kind = tup[0]
                if kind == 'field':
                    path    = strip_prefix(tup[1], implicit_base)
                    new_fields.append(('field', path, tup[2]))
                elif kind == 'aggregation':
                    func, param, alias = tup[1], tup[2], tup[3]
                    param = strip_prefix(param, implicit_base)
                    new_fields.append(('aggregation', func, param, alias))
                else:
                    new_fields.append(tup)
            fields = new_fields

    all_aggregations = all(field_type == 'aggregation' for field_type, *_ in fields)
    
    if all_aggregations and not group_by:
        selection = []

        def _wrap(expr: str) -> str:
            """Return a list literal [ expr ] unless it already is one."""
            return expr if expr.lstrip().startswith('[') else f'[ {expr} ]'

        for _, func, field_path, alias in fields:
            if base_selector:
                raw = f'{base_selector} | .{field_path}'
            elif '[]' in field_path:
                raw = f'.{field_path}'
            else:
                raw = f'.[] | .{field_path}'

            wrapped = _wrap(raw)

            if func == 'count' and field_path == '*':
                selection.append(f'"{alias}": length')
                continue

            if func == 'sum':
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) | add // 0)'
                )
            elif func == 'avg':
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) ' +
                    f'| if length>0 then add/length else null end)'
                )
            elif func == 'min':
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) ' +
                    f'| if length>0 then min else null end)'
                )
            elif func == 'max':
                selection.append(
                    f'"{alias}": ({wrapped} | map(select(type=="number")) ' +
                    f'| if length>0 then max else null end)'
                )
            elif func == 'count':
                selection.append(f'"{alias}": ({wrapped} | length)')

        jq_filter = f'{{ {", ".join(selection)} }}'

    elif group_by:
        group_keys = []
        for field in group_by:
            group_keys.append('.' + generate_jq_path(parse_path(field), False).lstrip('.'))
        group_key = ', '.join(group_keys)

        agg_selections = []
        for ft, *fd in fields:
            if ft == 'field':
                fld, alias = fd
                if fld in group_by:
                    agg_selections.append(f'"{alias}": .[0].{generate_jq_path(parse_path(fld), False).lstrip(".")}')
            else: 
                func, param, alias = fd
                agg_selections.append(f'"{alias}": {generate_jq_expression(Expression(ExprType.AGGREGATION, func, [param]), "group")}')

        prefix = f'[ {base_selector} ] | ' if base_selector else ''
        jq_filter = (
            f'{prefix}map(select(. != null)) | '
            f'group_by({group_key}) | '
            f'map({{ {", ".join(agg_selections)} }})'
        )

        if having:
            jq_filter += f' | map(select({process_having_condition(having)}))'

    else:
        if fields == [('field', '*', '*')]:
            if from_path:
                jq_filter = f'[{base_selector}]'
            else:
                jq_filter = '.'
        elif (not any(ftype == 'field' for ftype, *_ in fields) and not from_path and not group_by):
            selection = []
            for field_type, *field_data in fields:
                if field_type == 'aggregation':
                    func, field_path, alias = field_data
                    expr = Expression(ExprType.AGGREGATION, func, [field_path])
                    jq_expr = generate_jq_expression(expr, base_context)
                    selection.append(f'"{alias}": {jq_expr}')
                elif field_type == 'expression':
                    expression, alias = field_data
                    expr = parse_expression(expression)
                    jq_expr = generate_jq_expression(expr, base_context)
                    selection.append(f'"{alias}": {jq_expr}')
                elif field_type == 'direct_jq':
                    jq_expr, alias = field_data
                    selection.append(f'"{alias}": {jq_expr}')
            jq_filter = f'[{{ {", ".join(selection)} }}]'

        else:
            selection = []
            for field_type, *field_data in fields:
                if field_type == 'field':
                    field, alias = field_data
                    path = parse_path(field)
                    selection.append(f'"{alias}": ({generate_jq_path(path, base_context)} // null)')
                elif field_type == 'aggregation':
                    func, field_path, alias = field_data
                    expr = Expression(ExprType.AGGREGATION, func, [field_path])
                    jq_expr = generate_jq_expression(expr, base_context)
                    selection.append(f'"{alias}": {jq_expr}')
                elif field_type == 'expression':
                    expression, alias = field_data
                    expr = parse_expression(expression)
                    jq_expr = generate_jq_expression(expr, base_context)
                    selection.append(f'"{alias}": {jq_expr}')
                elif field_type == 'direct_jq':
                    jq_expr, alias = field_data
                    selection.append(f'"{alias}": {jq_expr}')
            map_filter = f'{{ {", ".join(selection)} }}'

            if from_path:
                if condition and isinstance(condition, str):
                    if "between" in condition.lower():
                        field, range_part = condition.split(" between ")
                        low, high = range_part.split(" and ")
                        cond_filter = f"(.{field.strip()} >= {low.strip()} and .{field.strip()} <= {high.strip()})"
                        jq_filter = f'[{base_selector} | select({cond_filter}) | {map_filter}]'
                    elif " contains " in condition.lower():
                        field, value = condition.split(" contains ")
                        value = value.strip()
                        if value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        cond_filter = f"(.{field.strip()} | tostring | contains(\"{value}\"))"
                        jq_filter = f'[{base_selector} | select({cond_filter}) | {map_filter}]'
                    else:
                        jq_filter = f'[{base_selector} | select({condition}) | {map_filter}]'
                else:
                    if condition:
                        jq_filter = f'[{base_selector} | select({condition}) | {map_filter}]'
                    else:
                        jq_filter = f'[{base_selector} | {map_filter}]'
            else:
                if condition:
                    jq_filter = (
                        f'if type == "array" then . | map(select({condition}) | {map_filter}) '
                        f'elif type == "object" then [select({condition}) | {map_filter}] '
                        f'elif type == "number" then if {condition} then [{{"value": .}}] else [] end '
                        f'elif type == "string" then if {condition} then [{{"value": .}}] else [] end '
                        f'else [] end'
                    )
                else:
                    jq_filter = (
                        f'if type == "array" then . | map({map_filter}) '
                        f'elif type == "object" then [{map_filter}] '
                        f'elif type == "number" then [{{"value": .}}] '
                        f'elif type == "string" then [{{"value": .}}] '
                        f'else [] end'
                    )

            if order_by:
                jq_filter += f' | sort_by(.{order_by})'
                if sort_direction == 'desc':
                    jq_filter += ' | reverse'
            if limit:
                jq_filter += f' | .[0:{limit}]'
    logging.info(f"Generated jq filter: {jq_filter}")
    return jq_filter
