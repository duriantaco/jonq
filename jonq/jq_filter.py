import re
import logging

logging.basicConfig(level=logging.INFO)

def format_field_path(field):
    if ' ' in field or not re.match(r'^[\w\.\[\]\-]+$', field):
        if '.' in field:
            parts = re.split(r'\.(?![^\[]*\])', field)
            formatted_parts = []
            for part in parts:
                if ' ' in part or not re.match(r'^[\w\[\]\-]+$', part):
                    safe_part = part.replace('"', '\\"')
                    formatted_parts.append(f'"{safe_part}"?')
                elif '[' in part and ']' in part:
                    array_match = re.match(r'(.*?)(\[\d+\])(.*)$', part)
                    if array_match:
                        pre, idx, post = array_match.groups()
                        if post:
                            formatted_parts.append(f"{pre}{idx}?{post}?")
                        else:
                            formatted_parts.append(f"{pre}{idx}?")
                    else:
                        formatted_parts.append(f"{part}?")
                else:
                    formatted_parts.append(f"{part}?")
            return ".".join(formatted_parts)
        else:
            safe_field = field.replace('"', '\\"')
            return f'"{safe_field}"?'
    elif '.' in field:
        parts = re.split(r'\.(?![^\[]*\])', field)
        formatted_parts = []
        for part in parts:
            if '[' in part and ']' in part:
                array_match = re.match(r'(.*?)(\[\d+\])(.*)$', part)
                if array_match:
                    pre, idx, post = array_match.groups()
                    if post:
                        formatted_parts.append(f"{pre}{idx}?{post}?")
                    else:
                        formatted_parts.append(f"{pre}{idx}?")
                else:
                    formatted_parts.append(f"{part}?")
            else:
                formatted_parts.append(f"{part}?")
        return ".".join(formatted_parts)
    elif '[' in field and ']' in field:
        array_match = re.match(r'(.*?)(\[\d+\])(.*)$', field)
        if array_match:
            pre, idx, post = array_match.groups()
            if post:
                return f"{pre}{idx}?{post}?"
            else:
                return f"{pre}{idx}?"
        else:
            return f"{field}?"
    else:
        return f"{field}?"

def build_jq_path(field_path):
    if not field_path or field_path == '*':
        return '.'
        
    parts = re.split(r'\.(?![^\[]*\])', field_path)
    jq_path = ''
    
    for i, part in enumerate(parts):
        if '[]' in part:
            before_array, *after_array = part.split('[]', 1)
            
            if i == 0:
                jq_path = '.' if not before_array else f'.{before_array}?'
            else:
                jq_path += '.' if not before_array else f'.{before_array}?'
                
            jq_path += '[]'
            
            if after_array and after_array[0]:
                jq_path += f'.{after_array[0]}?'
                
        elif '[' in part and ']' in part:
            array_match = re.match(r'([^[]*?)(\[\d+\])(.*)$', part)
            if array_match:
                pre, idx, post = array_match.groups()
                
                if i == 0:
                    jq_path = '.' if not pre else f'.{pre}?'
                else:
                    jq_path += '.' if not pre else f'.{pre}?'
                    
                jq_path += idx
                
                if post:
                    jq_path += f'.{post}?'
            else:
                if i == 0:
                    jq_path = f'.{part}?'
                else:
                    jq_path += f'.{part}?'
        else:
            if i == 0:
                jq_path = f'.{part}?'
            else:
                jq_path += f'.{part}?'
    
    return jq_path

def transform_nested_array_path(field_path):
    if '[]' not in field_path:
        return '.' + field_path.replace('.', '?.')
    
    segments = field_path.split('[]')
    
    result = []
    for i in range(len(segments) - 1):
        segment = segments[i]
        if segment:
            if i == 0:
                result.append('.' + segment.replace('.', '?.'))
            else:
                if segment.startswith('.'):
                    segment = segment[1:]
                result.append(' | .' + segment.replace('.', '?.'))
        result.append('[]')
    
    if segments[-1]:
        last = segments[-1]
        if last.startswith('.'):
            last = last[1:]
        result.append(' | .' + last.replace('.', '?.'))
    
    return ''.join(result)

def translate_expression(expression):
    def replace_agg(match):
        func, arg = match.group(1), match.group(2)
        if func == 'count' and arg.strip() == '*':
            return 'length'

        operation = None
        field_path = arg.strip()
        for op in ['+', '-', '*', '/']:
            if f' {op} ' in arg:
                field_path, value = [part.strip() for part in arg.split(f' {op} ', 1)]
                operation = (op, value)
                break

        if '[]' in field_path:
            transformed_path = transform_nested_array_path(field_path)
            if operation:
                op, val = operation
                base_expr = f'[{transformed_path} | (. {op} {val})]'
            else:
                base_expr = f'[{transformed_path}]'
        else:
            base_expr = f'[.{field_path}?]'
            if operation:
                op, val = operation
                base_expr = f'({base_expr} | map(. {op} {val}))'

        agg_base = f'{base_expr} | flatten | map(select(type == "number"))'
        if func == 'sum':
            return f'({agg_base} | add // 0)'
        elif func == 'avg':
            return f'({agg_base} | if length > 0 then (add / length) else null end)'
        elif func == 'max':
            return f'({agg_base} | if length > 0 then max else null end)'
        elif func == 'min':
            return f'({agg_base} | if length > 0 then min else null end)'
        else:
            return f'({base_expr} | length)'

    expression = re.sub(r'(\w+)\s*\(\s*([^)]+)\s*\)', replace_agg, expression)
    expression = expression.replace("count(*)", "length")
    return expression

def escape_string(s):
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        content = s[1:-1]
        escaped = content.replace('"', '\\"')
        return f'"{escaped}"'
    return s

def parse_condition(tokens, from_path=None):
    if not tokens:
        return None
        
    idx = 0
    while idx < len(tokens):
        if idx + 4 < len(tokens) and tokens[idx+1].lower() == 'between':
            field = tokens[idx]
            low = tokens[idx+2]
            if tokens[idx+3].lower() != 'and':
                raise ValueError(f"Expected 'AND' in BETWEEN operator at position {idx+3}")
            high = tokens[idx+4]
            
            if '[' in field:
                parts = field.split('[', 1)
                base = parts[0]
                rest = '[' + parts[1]
                field_ref = f'.{base}{rest}'
            else:
                field_ref = f'.{field}'
                
            tokens[idx:idx+5] = [f"({field_ref} != null and {field_ref} >= {low} and {field_ref} <= {high})"]
            continue
            
        if idx + 2 < len(tokens) and tokens[idx+1].lower() == 'contains':
            field = tokens[idx]
            value = tokens[idx+2]
            
            if '[' in field:
                parts = field.split('[', 1)
                base = parts[0]
                rest = '[' + parts[1]
                field_ref = f'.{base}{rest}'
            else:
                field_ref = f'.{field}'
                
            if value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
                tokens[idx:idx+3] = [f"({field_ref} != null and ({field_ref} | type == \"string\" or {field_ref} | type == \"number\") and ({field_ref} | tostring) | contains(\"{value}\"))"]
            else:
                tokens[idx:idx+3] = [f"({field_ref} != null and ({field_ref} | type == \"string\" or {field_ref} | type == \"number\") and ({field_ref} | tostring) | contains(({value} | tostring)))"]
            continue
            
        idx += 1
    
    condition_str = " ".join(tokens)
    condition_str = re.sub(r"'([^']*)'", r'"\1"', condition_str)
    condition_str = condition_str.replace(" = = ", " == ").replace("==", " == ")
    
    for match in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:\[[0-9]+\])?(?:\.[a-zA-Z_][a-zA-Z0-9_]*(?:\[[0-9]+\])?)*)\b', condition_str):
        field = match.group(1)
        if field not in ["and", "or", "null", "true", "false"] and not field.isdigit() and not field.startswith('.'):
            if '[]' in field:
                parts = field.split('[]', 1)
                array_path = parts[0] + '[]'
                subfield = parts[1][1:] if parts[1] and parts[1].startswith('.') else parts[1]
                condition_str = re.sub(
                    r'\b{}\b'.format(re.escape(field)),
                    f'any({array_path}; .{subfield})',
                    condition_str
                )
            elif '[' in field:
                parts = field.split('[', 1)
                base = parts[0]
                rest = '[' + parts[1]
                pattern = r'\b{}\b'.format(re.escape(field))
                replacement = f'.{base}{rest}'
                condition_str = re.sub(pattern, replacement, condition_str)
            else:
                pattern = r'\b{}\b'.format(re.escape(field))
                condition_str = re.sub(pattern, f'.{field}', condition_str)
    
    return condition_str

def generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path=None):
    base_selector = ''
    if from_path:
        if from_path == '[]':
            base_selector = '.[]'
        elif from_path.startswith('[]'):
            nested_path = from_path[2:]
            if nested_path.startswith('.'):
                nested_path = nested_path[1:]
            base_selector = f'.[] | .{nested_path}[]'
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
        else:
            base_selector = f'.{from_path}'
    
    all_aggregations = all(field_type == 'aggregation' for field_type, *_ in fields)
    
    if all_aggregations and not group_by:
        selection = []
        for _, func, field_path, alias in fields:
            if func == 'count' and field_path == '*':
                selection.append(f'"{alias}": length')
                continue
                
            if '[]' in field_path:
                transformed_path = transform_nested_array_path(field_path)
                
                if func == 'count':
                    agg_expr = f'([{transformed_path}] | length)'
                else:
                    if func == 'sum':
                        agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | add // 0)'
                    elif func == 'avg':
                        agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | if length > 0 then (add / length) else null end)'
                    elif func == 'max':
                        agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | if length > 0 then max else null end)'
                    elif func == 'min':
                        agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | if length > 0 then min else null end)'
                    else:
                        agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | {func})'
            else:
                if func == 'count':
                    if field_path == '*':
                        agg_expr = 'length'
                    else:
                        agg_expr = f'([.[] | .{field_path}] | length)'
                else:
                    if func == 'sum':
                        agg_expr = f'([.[] | .{field_path} | select(type == "number")] | add // 0)'
                    elif func == 'avg':
                        agg_expr = f'([.[] | .{field_path} | select(type == "number")] | if length > 0 then (add / length) else null end)'
                    elif func == 'max':
                        agg_expr = f'([.[] | .{field_path} | select(type == "number")] | if length > 0 then max else null end)'
                    elif func == 'min':
                        agg_expr = f'([.[] | .{field_path} | select(type == "number")] | if length > 0 then min else null end)'
                    else:
                        agg_expr = f'([.[] | .{field_path} | select(type == "number")] | {func})'
                
            selection.append(f'"{alias}": {agg_expr}')
        jq_filter = f'{{ {", ".join(selection)} }}'
            
    elif group_by:
        group_keys = []
        for field in group_by:
            if ' ' in field or not re.match(r'^[\w\.\[\]\-]+$', field):
                safe_field = field.replace('"', '\\"')
                group_keys.append(f'."{safe_field}"')
            else:
                group_keys.append(f'.{field}')
        
        group_key = ', '.join(group_keys)
        
        agg_selections = []
        for field_type, *field_data in fields:
            if field_type == 'field':
                field, alias = field_data
                if field in group_by:
                    if ' ' in field or not re.match(r'^[\w\.\[\]\-]+$', field):
                        safe_field = field.replace('"', '\\"')
                        agg_selections.append(f'"{alias}": .[0]."{safe_field}"')
                    else:
                        agg_selections.append(f'"{alias}": .[0].{field}')
            elif field_type == 'aggregation':
                func, field_path, alias = field_data
                if func == 'count' and field_path == '*':
                    agg_selections.append(f'"{alias}": length')
                elif func == 'count':
                    if '[]' in field_path:
                        transformed_path = transform_nested_array_path(field_path)
                        agg_selections.append(f'"{alias}": (map([{transformed_path}] | length) | add // 0)')
                    else:
                        agg_selections.append(f'"{alias}": (map(.{field_path} | if type == "array" then length else 0 end) | add // 0)')
                elif func in ['sum', 'avg', 'min', 'max']:
                    if '[]' in field_path:
                        transformed_path = transform_nested_array_path(field_path)
                        mapped_values = f'map([{transformed_path}] | flatten | map(select(type == "number")))'
                        
                        if func == 'sum':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | add // 0)')
                        elif func == 'avg':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | if length > 0 then (add / length) else null end)')
                        elif func == 'max':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | if length > 0 then max else null end)')
                        elif func == 'min':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | if length > 0 then min else null end)')
                    else:
                        mapped_values = f'map(.{field_path} | if type == "array" then (map(select(type == "number")) | add // []) else select(type == "number") end)'
                        
                        if func == 'sum':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | add // 0)')
                        elif func == 'avg':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | if length > 0 then (add / length) else null end)')
                        elif func == 'max':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | if length > 0 then max else null end)')
                        elif func == 'min':
                            agg_selections.append(f'"{alias}": ({mapped_values} | flatten | if length > 0 then min else null end)')
        
        if from_path:
            if '[]' in from_path:
                jq_filter = f'[{base_selector}] | map(select(. != null)) | group_by({group_key}) | map({{ {", ".join(agg_selections)} }})'
            else:
                jq_filter = f'. | map(select(. != null)) | group_by({group_key}) | map({{ {", ".join(agg_selections)} }})'
        else:
            jq_filter = f'. | map(select(. != null)) | group_by({group_key}) | map({{ {", ".join(agg_selections)} }})'

        if having:
            jq_filter += f' | map(select({having}))'
    else:
        if fields == [('field', '*', '*')]:
            if from_path:
                jq_filter = f'[{base_selector}]'
            else:
                jq_filter = '.'
        else:
            selection = []
            for field_type, *field_data in fields:
                if field_type == 'field':
                    field, alias = field_data
                    if ' ' in field or not re.match(r'^[\w\.\[\]\-]+$', field):
                        safe_field = field.replace('"', '\\"')
                        selection.append(f'"{alias}": (."{safe_field}" // null)')
                    else:
                        formatted_path = format_field_path(field)
                        selection.append(f'"{alias}": (.{formatted_path} // null)')
                elif field_type == 'aggregation':
                    func, field_path, alias = field_data
                    if func == 'count' and field_path == '*':
                        selection.append(f'"{alias}": length')
                    elif func == 'count':
                        if '[]' in field_path:
                            transformed_path = transform_nested_array_path(field_path)
                            agg_expr = f'([{transformed_path}] | length)'
                            selection.append(f'"{alias}": {agg_expr}')
                        else:
                            agg_expr = f'(.{field_path} | if type == "array" then length else 0 end)'
                            selection.append(f'"{alias}": {agg_expr}')
                    else:
                        if '[]' in field_path:
                            transformed_path = transform_nested_array_path(field_path)
                            
                            if func == 'sum':
                                agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | add // 0)'
                            elif func == 'avg':
                                agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | if length > 0 then (add / length) else null end)'
                            elif func == 'max':
                                agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | if length > 0 then max else null end)'
                            elif func == 'min':
                                agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | if length > 0 then min else null end)'
                            else:
                                agg_expr = f'([{transformed_path}] | flatten | map(select(type == "number")) | {func})'
                            selection.append(f'"{alias}": {agg_expr}')
                        elif '.' in field_path:
                            array_part, field_part = field_path.rsplit('.', 1)
                            mapped_values = f'(.{array_part} | if type == "array" then map(.{field_part} | select(type == "number")) else [] end)'
                            
                            if func == 'sum':
                                agg_expr = f'({mapped_values} | add // 0)'
                            elif func == 'avg':
                                agg_expr = f'({mapped_values} | if length > 0 then (add / length) else null end)'
                            elif func == 'max':
                                agg_expr = f'({mapped_values} | if length > 0 then max else null end)'
                            elif func == 'min':
                                agg_expr = f'({mapped_values} | if length > 0 then min else null end)'
                            else:
                                agg_expr = f'({mapped_values} | {func})'
                            selection.append(f'"{alias}": {agg_expr}')
                        else:
                            mapped_values = f'(.{field_path} | if type == "array" then map(select(type == "number")) else (if type == "number" then [.] else [] end) end)'
                            
                            if func == 'sum':
                                agg_expr = f'({mapped_values} | add // 0)'
                            elif func == 'avg':
                                agg_expr = f'({mapped_values} | if length > 0 then (add / length) else null end)'
                            elif func == 'max':
                                agg_expr = f'({mapped_values} | if length > 0 then max else null end)'
                            elif func == 'min':
                                agg_expr = f'({mapped_values} | if length > 0 then min else null end)'
                            else:
                                agg_expr = f'({mapped_values} | {func})'
                            selection.append(f'"{alias}": {agg_expr}')
                elif field_type == 'expression':
                    expression, alias = field_data
                    if (expression.startswith("'") and expression.endswith("'")) or \
                       (expression.startswith('"') and expression.endswith('"')):
                        field_name = expression[1:-1]
                        safe_field = field_name.replace('"', '\\"')
                        selection.append(f'"{alias}": (."{safe_field}" // null)')
                    else:
                        expression = expression.replace("count(*)", "length")
                        
                        if '-' in expression or '+' in expression or '*' in expression or '/' in expression:
                            for op in ['-', '+', '*', '/']:
                                if f" {op} " in expression:
                                    parts = expression.split(f" {op} ")
                                    expr1 = translate_expression(parts[0])
                                    expr2 = translate_expression(parts[1])
                                    expression = f"({expr1} // 0) {op} ({expr2} // 0)"
                                    break
                        else:
                            expression = translate_expression(expression)
                            
                        selection.append(f'"{alias}": ({expression})')
            
            map_filter = f'{{ {", ".join(selection)} }}'
            
            if from_path:
                if condition:
                
                    condition_str = condition
                    
                    for match in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*\()', condition_str):
                        field = match.group(1)
                        if field not in ["and", "or", "null", "true", "false"] and not field.isdigit() and not field.startswith('.'):
                            pattern = r'\b{}\b'.format(re.escape(field))
                            replacement = f'.{field}'
                            condition_str = re.sub(pattern, replacement, condition_str)
                    
                    jq_filter = f'[{base_selector} | select({condition_str}) | {map_filter}]'
                else:
                    jq_filter = f'[{base_selector} | {map_filter}]'
            else:
                if condition:
                    jq_filter = (
                        f'if type == "array" then '
                        f'. | map(select({condition}) | {map_filter}) '
                        f'else [{map_filter}] end'
                    )
                else:
                    jq_filter = (
                        f'if type == "array" then '
                        f'. | map({map_filter}) '
                        f'else [{map_filter}] end'
                    )
            
            if order_by:
                jq_filter += f' | sort_by(.{order_by})'
                if sort_direction == 'desc':
                    jq_filter += ' | reverse'
            if limit:
                jq_filter += f' | .[0:{limit}]'
    
    logging.info(f"Generated jq filter: {jq_filter}")
    return jq_filter