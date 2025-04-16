import re
import logging
import json

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
        func, field_path = match.group(1), match.group(2)
        if field_path == '*':
            if func == 'count':
                return 'length'
            else:
                raise ValueError(f"Function {func} cannot be used with '*'")
                
        if '[]' in field_path:
            transformed_path = transform_nested_array_path(field_path)
            
            if func == 'sum':
                return f'([{transformed_path}] | map(select(type == "number")) | add)'
            elif func == 'avg':
                return f'([{transformed_path}] | map(select(type == "number")) | if length > 0 then add / length else null end)'
            elif func in ['max', 'min']:
                return f'([{transformed_path}] | map(select(type == "number")) | {func})'
            else:
                return f'([{transformed_path}] | length)'
        
        if '.' in field_path:
            array_part, field_part = field_path.rsplit('.', 1)
            return f'(if type == "array" then [.[] | .{field_path}?] else [.{array_part}[] | .{field_part}?] end | map(select(type == "number")) | {func_mapping(func)})'
        else:
            return f'(if type == "array" then [.[] | .{field_path}?] else [.{field_path}?] end | map(select(type == "number")) | {func_mapping(func)})'
    
    def func_mapping(func):
        if func == 'sum':
            return 'add'
        elif func == 'avg':
            return 'if length > 0 then add / length else null end'
        elif func == 'count':
            return 'length'
        else: 
            return func
    
    return re.sub(r'(\w+)\(([\w\.\[\]\*]+)\)', replace_agg, expression)

def escape_string(s):
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        content = s[1:-1]
        escaped = content.replace('"', '\\"')
        return f'"{escaped}"'
    return s

def generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path=None):
    if from_path:
        if from_path == '[]':
            base_selector = '.[]'
        elif from_path.startswith('[]'):
            nested_path = from_path[2:]
            if nested_path.startswith('.'):
                nested_path = nested_path[1:]
            
            base_selector = f'.[] | .{nested_path}[]'
        elif '[]' in from_path:
            clean_path = from_path.replace('[]', '')
            if clean_path.startswith('.'):
                clean_path = clean_path[1:]
            base_selector = f'.{clean_path}[]'
        else:
            base_selector = f'.{from_path}[]'
    
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
                        agg_expr = f'([{transformed_path}] | map(select(type == "number")) | add)'
                    elif func == 'avg':
                        agg_expr = f'([{transformed_path}] | map(select(type == "number")) | if length > 0 then add / length else null end)'
                    else:
                        agg_expr = f'([{transformed_path}] | map(select(type == "number")) | {func})'
            else:
                if '.' in field_path:
                    array_part, field_part = field_path.rsplit('.', 1)
                    agg_expr = f'(if type == "array" then [.[] | .{field_path}?] else [.{array_part}[] | .{field_part}?] end | map(select(type == "number"))'
                    
                    if func == 'sum':
                        agg_expr += ' | add)'
                    elif func == 'avg':
                        agg_expr += ' | if length > 0 then add / length else null end)'
                    else:
                        agg_expr += f' | {func})'
                else:
                    agg_expr = f'(if type == "array" then [.[] | .{field_path}?] else [.{field_path}?] end | map(select(type == "number"))'
                    
                    if func == 'sum':
                        agg_expr += ' | add)'
                    elif func == 'avg':
                        agg_expr += ' | if length > 0 then add / length else null end)'
                    elif func == 'count':
                        agg_expr = f'(if type == "array" then [.[] | .{field_path}?] else [.{field_path}?] end | length)'
                    else:
                        agg_expr += f' | {func})'
                
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
                        agg_selections.append(f'"{alias}": (map([{transformed_path}] | length) | add)')
                    else:
                        agg_selections.append(f'"{alias}": (map([.{field_path}?] | length) | add)')
                elif func in ['sum', 'avg', 'min', 'max']:
                    if '[]' in field_path:
                        transformed_path = transform_nested_array_path(field_path)
                        mapped_values = f'map([{transformed_path}] | map(select(type == "number")))'
                        
                        if func == 'sum':
                            agg_selections.append(f'"{alias}": ({mapped_values} | add)')
                        elif func == 'avg':
                            agg_selections.append(f'"{alias}": ({mapped_values} | if length > 0 then add / length else null end)')
                        else:
                            agg_selections.append(f'"{alias}": ({mapped_values} | {func})')
                    else:
                        mapped_values = f'map(.{field_path}? | select(type == "number"))'
                        
                        if func == 'sum':
                            agg_selections.append(f'"{alias}": ({mapped_values} | add)')
                        elif func == 'avg':
                            agg_selections.append(f'"{alias}": ({mapped_values} | if length > 0 then add / length else null end)')
                        else:
                            agg_selections.append(f'"{alias}": ({mapped_values} | {func})')
        
        if from_path:
            jq_filter = f'[{base_selector}] | map(select(. != null)) | group_by({group_key}) | map({{ {", ".join(agg_selections)} }})'
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
                        selection.append(f'"{alias}": (."{safe_field}"? // null)')
                    else:
                        formatted_path = format_field_path(field)
                        selection.append(f'{json.dumps(alias)}: (.{formatted_path} // null)')
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
                            field_expr = build_jq_path(field_path)
                            agg_expr = f'([{field_expr}] | length)'
                            selection.append(f'"{alias}": {agg_expr}')
                    else:
                        if '[]' in field_path:
                            transformed_path = transform_nested_array_path(field_path)
                            
                            if func == 'sum':
                                agg_expr = f'([{transformed_path}] | map(select(type == "number")) | add)'
                            elif func == 'avg':
                                agg_expr = f'([{transformed_path}] | map(select(type == "number")) | if length > 0 then add / length else null end)'
                            else:
                                agg_expr = f'([{transformed_path}] | map(select(type == "number")) | {func})'
                            selection.append(f'"{alias}": {agg_expr}')
                        elif '.' in field_path:
                            array_part, field_part = field_path.rsplit('.', 1)
                            mapped_values = f'[.{array_part}[] | .{field_part}?] | map(select(type == "number"))'
                            if func == 'sum':
                                agg_expr = f'({mapped_values} | add)'
                            elif func == 'avg':
                                agg_expr = f'({mapped_values} | if length > 0 then add / length else null end)'
                            else:
                                agg_expr = f'({mapped_values} | {func})'
                            selection.append(f'"{alias}": {agg_expr}')
                        else:
                            mapped_values = f'[.{field_path}?] | map(select(type == "number"))'
                            if func == 'sum':
                                agg_expr = f'({mapped_values} | add)'
                            elif func == 'avg':
                                agg_expr = f'({mapped_values} | if length > 0 then add / length else null end)'
                            else:
                                agg_expr = f'({mapped_values} | {func})'
                            selection.append(f'"{alias}": {agg_expr}')
                elif field_type == 'expression':
                    expression, alias = field_data
                    if (expression.startswith("'") and expression.endswith("'")) or \
                       (expression.startswith('"') and expression.endswith('"')):
                        field_name = expression[1:-1]
                        safe_field = field_name.replace('"', '\\"')
                        selection.append(f'"{alias}": (."{safe_field}"? // null)')
                    else:
                        translated_expr = translate_expression(expression)
                        selection.append(f'"{alias}": ({translated_expr})')
            
            map_filter = f'{{ {", ".join(selection)} }}'
            
            if from_path:
                if condition:
                    jq_filter = f'[{base_selector} | select({condition}) | {map_filter}]'
                else:
                    jq_filter = f'[{base_selector} | {map_filter}]'
            else:
                if condition:
                    jq_filter = (
                        f'if type == "array" then '
                        f'. | map(select({condition}) | {map_filter}) '
                        f'elif type == "object" then '
                        f'[select({condition}) | {map_filter}] '
                        f'elif type == "number" then '
                        f'if {condition} then [{{"value": .}}] else [] end '
                        f'elif type == "string" then '
                        f'if {condition} then [{{"value": .}}] else [] end '
                        f'else [] end'
                    )
                else:
                    jq_filter = (
                        f'if type == "array" then '
                        f'. | map({map_filter}) '
                        f'elif type == "object" then '
                        f'[{map_filter}] '
                        f'elif type == "number" then '
                        f'[{{"value": .}}] '
                        f'elif type == "string" then '
                        f'[{{"value": .}}] '
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