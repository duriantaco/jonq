import logging
import re
from jonq.ast import *
from jonq.parser import parse_path, parse_expression

logger = logging.getLogger(__name__)

_HAVING_REPLACEMENTS = {
    'avg_age': '.avg_age',
    'count': '.count',
    'avg_monthly': '.avg_monthly',
    'total_revenue': '.total_revenue',
    'avg_price': '.avg_price',
    'total_price': '.total_price',
    'min_age': '.min_age',
    'max_age': '.max_age',
    'avg_profit': '.avg_profit',
    'total_spent': '.total_spent',
    'total_orders': '.total_orders',
    'price_order_ratio': '.price_order_ratio',
    'user_count': '.user_count',
    'version_count': '.version_count',
    'customer_count': '.customer_count',
    'avg_yearly': '.avg_yearly',
    'price_range': '.price_range',
    'avg_monthly_price': '.avg_monthly_price',
}

_HAVING_REGEXES = {
    key: re.compile(rf'\b{key}\b') for key in _HAVING_REPLACEMENTS
}

def _quote(name: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return name
    return '"' + name.replace('"', r'\"') + '"'

def generate_jq_path(path, context="root", null_check=True):
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
                return (
                    f"([{arg_jq}] | flatten | map(select(type == \"number\")) "
                    f"| add // 0)  # sum"
                )
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
                    return f"([.[] | {arg_jq} | select(type == \"number\")] | add // 0) # sum"
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
        return f"({left} {op} {right})"
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
    
    for key, pattern in _HAVING_REGEXES.items():
        having = pattern.sub(_HAVING_REPLACEMENTS[key], having)
    
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
    pieces = []
    remaining = path_with_arrays.lstrip('.')
    while '[]' in remaining:
        pre, remaining = remaining.split('[]', 1)
        pre = pre.lstrip('.')
        pieces.append(f'.{pre}[]')
        if remaining.startswith('.'):
            remaining = remaining[1:]
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
            base = f'.{parts[0].lstrip(".")}' if parts[0] else '.'
            rest = parts[1].lstrip('.') if len(parts) > 1 else ''
            base_selector = f'{base}[]' + (f' | .{rest}' if rest else '')
            base_context = "array"
        else:
            base_selector = f'.{from_path}'
            base_context = "object"
    if not from_path and group_by and any('[]' in g for g in group_by):
        implicit_base, _ = split_base_array(group_by[0])
        base_selector = make_selector_from_path(group_by[0])
        base_context = "array"
        group_by = [g.split('[]')[-1].lstrip('.') for g in group_by]
        new_fields = []
        for tup in fields:
            if tup[0] == 'field':
                path, alias = tup[1:]
                if '[]' in path:
                    path = strip_prefix(path, implicit_base).split('[]')[-1].lstrip('.')
                new_fields.append(('field', path, alias))
            elif tup[0] == 'aggregation':
                func, param, alias = tup[1:]
                if '[]' in param:
                    param = strip_prefix(param, implicit_base)
                new_fields.append(('aggregation', func, param, alias))
            else:
                new_fields.append(tup)
        fields = new_fields
    if not from_path and not group_by:
        first_param_with_array = next(
            (tup[2] for tup in fields if tup[0] == 'aggregation' and '[]' in tup[2]),
            None,
        )
        if first_param_with_array:
            implicit_base, _ = split_base_array(first_param_with_array)
            base_selector = f'.{implicit_base}[]'
            base_context = "array"
            fields = [
                ('aggregation', func, strip_prefix(param, implicit_base), alias)
                if ftype == 'aggregation' else tup
                for tup in fields
                for ftype, func, param, alias in [tup] if ftype == 'aggregation'
            ] + [tup for tup in fields if tup[0] != 'aggregation']
    all_aggregations = all(ft == 'aggregation' for ft, *_ in fields)
    if all_aggregations and not group_by:
        base_data = base_selector or '(if type=="array" then .[] else . end)'
        if condition:
            base_data += f' | select({condition})'
        def wrap(expr): return expr if expr.lstrip().startswith('[') else f'[ {expr} ]'
        selection = []
        for _, func, param, alias in fields:
            raw = f'{base_data} | .{param.lstrip(".")}'
            wrapped = wrap(raw)
            if func == 'count' and param == '*':
                selection.append(f'"{alias}": length'); continue
            if func == 'sum':
                selection.append(f'"{alias}": ({wrapped} | map(select(type=="number")) | add // 0)')
            elif func == 'avg':
                selection.append(f'"{alias}": ({wrapped} | map(select(type=="number")) | if length>0 then add/length else null end)')
            elif func == 'min':
                selection.append(f'"{alias}": ({wrapped} | map(select(type=="number")) | if length>0 then min else null end)')
            elif func == 'max':
                selection.append(f'"{alias}": ({wrapped} | map(select(type=="number")) | if length>0 then max else null end)')
            elif func == 'count':
                selection.append(f'"{alias}": ({wrapped} | length)')
        jq_filter = f'{{ {", ".join(selection)} }}'
    elif group_by:
        group_keys = [generate_jq_path(parse_path(g), context="root", null_check=False) for g in group_by]
        group_key = ', '.join(group_keys)
        agg_sel = []
        for ftype, *data in fields:
            if ftype == 'field':
                fld, alias = data
                path = generate_jq_path(parse_path(fld), context="root", null_check=False).lstrip('.')
                agg_sel.append(f'"{alias}": .[0].{path}')
            elif ftype == 'aggregation':
                func, param, alias = data
                expr = Expression(ExprType.AGGREGATION, func, [param])
                agg_sel.append(f'"{alias}": {generate_jq_expression(expr,"group")}')
            elif ftype == 'expression':
                expr_txt, alias = data
                expr = parse_expression(expr_txt)
                agg_sel.append(f'"{alias}": {generate_jq_expression(expr,"group")}')
        prefix = f'[ {base_selector} ] | ' if base_selector else '[ .[] ] | '
        jq_filter = f'{prefix}map(select(. != null)) | group_by({group_key}) | map({{ {", ".join(agg_sel)} }})'
        if having:
            jq_filter += f' | map(select({process_having_condition(having)}))'
    else:
        if fields == [('field', '*', '*')]:
            jq_filter = f'[{base_selector}]' if from_path else '.'
        elif not any(ft[0] == 'field' for ft in fields) and not from_path and not group_by:
            sel = []
            for ftype, *data in fields:
                if ftype == 'aggregation':
                    func, param, alias = data
                    sel.append(f'"{alias}": {generate_jq_expression(Expression(ExprType.AGGREGATION,func,[param]),base_context)}')
                elif ftype == 'expression':
                    expr_txt, alias = data
                    sel.append(f'"{alias}": {generate_jq_expression(parse_expression(expr_txt),base_context)}')
                elif ftype == 'direct_jq':
                    jq_expr, alias = data
                    sel.append(f'"{alias}": {jq_expr}')
            jq_filter = f'[{{ {", ".join(sel)} }}]'
        else:
            sel = []
            for ftype, *data in fields:
                if ftype == 'field':
                    field, alias = data
                    sel.append(f'"{alias}": ({generate_jq_path(parse_path(field),base_context)} // null)')
                elif ftype == 'aggregation':
                    func, param, alias = data
                    sel.append(f'"{alias}": {generate_jq_expression(Expression(ExprType.AGGREGATION,func,[param]),base_context)}')
                elif ftype == 'expression':
                    expr_txt, alias = data
                    sel.append(f'"{alias}": {generate_jq_expression(parse_expression(expr_txt),base_context)}')
                elif ftype == 'direct_jq':
                    jq_expr, alias = data
                    sel.append(f'"{alias}": {jq_expr}')
            map_filter = f'{{ {", ".join(sel)} }}'
            if from_path:
                body = f'{base_selector} | ' + ('select({}) | '.format(condition) if condition else '') + map_filter
                jq_filter = f'[ {body} ]'
            else:
                if condition:
                    jq_filter = (
                        f'if type=="array" then . | map(select({condition}) | {map_filter}) '
                        f'elif type=="object" then [select({condition}) | {map_filter}] '
                        f'elif type=="number" then if {condition} then [{{"value":.}}] else [] end '
                        f'elif type=="string" then if {condition} then [{{"value":.}}] else [] end '
                        f'else [] end'
                    )
                else:
                    jq_filter = (
                        f'if type=="array" then . | map({map_filter}) '
                        f'elif type=="object" then [{map_filter}] '
                        f'elif type=="number" then [{{"value":.}}] '
                        f'elif type=="string" then [{{"value":.}}] '
                        f'else [] end'
                    )
            if order_by:
                jq_filter += f' | sort_by(.{order_by})' + (' | reverse' if sort_direction == 'desc' else '')
            if limit:
                jq_filter += f' | .[0:{limit}]'
    logging.info(f"Generated jq filter: {jq_filter}")
    return jq_filter
