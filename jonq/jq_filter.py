import re
import logging
import json

logging.basicConfig(level=logging.INFO)

def format_field_path(field):
    """Format a field path for use in JQ filters with optional null-check operator.

    Args:
        field (str): The field path to format. Can include:
            - Simple field names (e.g., "name")
            - Nested paths with dots (e.g., "user.address.street")
            - Array indices (e.g., "users[0].name")
            - Spaces or special characters (e.g., "first name")

    Returns:
        str: The formatted field path with appropriate null-check operators and
            escaped characters. 
    """
    if ' ' in field or not re.match(r'^[\w\.\[\]]+$', field):
        if '.' in field:
            parts = re.split(r'\.(?![^\[]*\])', field)
            formatted_parts = []
            for part in parts:
                if ' ' in part or not re.match(r'^[\w\[\]]+$', part):
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
    parts = re.split(r'\.(?![^\[]*\])', field_path)
    jq_path = ''
    for idx, part in enumerate(parts):
        if '[' in part and ']' in part:
            array_match = re.match(r'(.*?)(\[\d+\])(.*)', part)
            if array_match:
                pre, idx, post = array_match.groups()
                if idx == 0:
                    jq_path = f'.{pre}{idx}{post}?'
                else:
                    jq_path += f'.{pre}{idx}{post}?'
            else:
                if idx == 0:
                    jq_path = f'.{part}?'
                else:
                    jq_path += f'.{part}?'
        else:
            if idx == 0:
                jq_path = f'.{part}?'
            else:
                jq_path += f'.{part}?'
    return jq_path

def translate_expression(expression):
    def replace_agg(match):
        func, field_path = match.group(1), match.group(2)
        if field_path == '*':
            if func == 'count':
                return 'length'
            else:
                raise ValueError(f"Function {func} cannot be used with '*'")
                
        if '.' in field_path:
            array_part, field_part = field_path.rsplit('.', 1)
            if func == 'sum':
                return f'(.{array_part}? | map(.{field_part}?) | map(select(type == "number"))) | add'
            elif func == 'avg':
                return f'(.{array_part}? | map(.{field_part}?) | map(select(type == "number"))) | add / length'
            elif func in ['max', 'min']:
                return f'(.{array_part}[]? | .{field_part}? | select(type == "number") | {func})'
            else:
                return f'(.{array_part}[]? | .{field_part}? | select(type == "number")) | {func}'
        else:
            agg_path = build_jq_path(field_path)
            mapped_values = f'({agg_path} | map(select(type == "number")))'
            if func == 'sum':
                return f'{mapped_values} | add'
            elif func == 'avg':
                return f'{mapped_values} | add / length'
            elif func in ['max', 'min']:
                return f'{mapped_values} | {func}'
        raise ValueError(f"Unsupported function: {func}")
    return re.sub(r'(\w+)\(([\w\.\[\]\*]+)\)', replace_agg, expression)

def escape_string(s):
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        content = s[1:-1]
        escaped = content.replace('"', '\\"')
        return f'"{escaped}"'
    return s

def generate_jq_filter(fields, condition, group_by, order_by, sort_direction, limit):
    """
    This function is one of the core properties of jonq. It creates a JQ filter for the data operations below:
    - Select
    - Count, Sum, Avg, Min, Max
    - Filtering based on conditions (Where)
    - Grouping
    - Sorting
    - Limiting results
    Parameters:
        fields (list): List of tuples describing the fields to select. Each tuple can be:
            - ('field', field_name, alias) for simple field selection
            - ('aggregation', func, field_path, alias) for aggregation operations
            - ('expression', expression, alias) for custom expressions
        condition (str, optional): Filter condition in JQ syntax. Defaults to None.
        group_by (list, optional): List of fields to group by. Defaults to None.
        order_by (str, optional): Field to sort by. Defaults to None.
        sort_direction (str, optional): Sort direction ('asc' or 'desc'). Defaults to None.
        limit (int, optional): Maximum number of results to return. Defaults to None.
    Returns:
        str: A JQ filter string that can be used to transform JSON data according to the specified parameters.
    """
    all_aggregations = all(field_type == 'aggregation' for field_type, *_ in fields)
    
    if all_aggregations and not group_by:
        selection = []
        for _, func, field_path, alias in fields:
            if func == 'count' and field_path == '*':
                selection.append(f'"{alias}": length')
                continue
                
            if '.' in field_path:
                array_field, value_field = field_path.rsplit('.', 1)
                if condition:
                    selected_values = f'[.[] | select({condition}) | .{array_field}?[] | .{value_field}?]'
                else:
                    selected_values = f'[.[] | .{array_field}?[] | .{value_field}?]'
            else:
                if condition:
                    selected_values = f'[.[] | select({condition}) | .{field_path}?]'
                else:
                    selected_values = f'[.[] | .{field_path}?]'
            if func == 'count':
                agg_expr = f'({selected_values} | map(select(. != null)) | length)'
            else:
                mapped_values = f'{selected_values} | map(select(type == "number"))'
                if func == 'sum':
                    agg_expr = f'({mapped_values} | add)'
                elif func == 'avg':
                    agg_expr = f'({mapped_values} | if length > 0 then add / length else null end)'
                else:
                    agg_expr = f'({mapped_values} | {func})'
            selection.append(f'"{alias}": {agg_expr}')
        jq_filter = f'{{ {", ".join(selection)} }}'
    elif group_by:
        group_keys = []
        for field in group_by:
            if ' ' in field or not re.match(r'^[\w\.\[\]]+$', field):
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
                    if ' ' in field or not re.match(r'^[\w\.\[\]]+$', field):
                        safe_field = field.replace('"', '\\"')
                        agg_selections.append(f'"{alias}": .[0]."{safe_field}"')
                    else:
                        agg_selections.append(f'"{alias}": .[0].{field}')
            elif field_type == 'aggregation':
                func, field_path, alias = field_data
                if func == 'count' and field_path == '*':
                    agg_selections.append(f'"{alias}": length')
                elif func == 'count':
                    if '.' in field_path:
                        agg_selections.append(f'"{alias}": (map(.{field_path}? | select(. != null) | length) | add)')
                    else:
                        agg_selections.append(f'"{alias}": (map(.{field_path}? | select(. != null) | length) | add)')
                elif func in ['sum', 'avg', 'min', 'max']:
                    if '.' in field_path:
                        array_part, field_part = field_path.rsplit('.', 1)
                        mapped_values = f'map(.{array_part}[]? | .{field_part}? | select(type == "number"))'
                        
                        if func == 'sum':
                            agg_selections.append(f'"{alias}": ({mapped_values} | add)')
                        elif func == 'avg':
                            agg_selections.append(f'"{alias}": ({mapped_values} | if length > 0 then add / length else null end)')
                        else:
                            agg_selections.append(f'"{alias}": ({mapped_values} | {func})')
                    else:
                        mapped_values = f'map(.{field_path}? // null)'
                        
                        if func == 'sum':
                            agg_selections.append(f'"{alias}": ({mapped_values} | map(select(type == "number")) | add)')
                        elif func == 'avg':
                            agg_selections.append(f'"{alias}": ({mapped_values} | map(select(type == "number")) | add / length)')
                        else:
                            agg_selections.append(f'"{alias}": ({mapped_values} | map(select(type == "number")) | {func})')
        
        jq_filter = f'. | map(select(. != null)) | group_by({group_key}) | map({{ {", ".join(agg_selections)} }})'
    else:
        if fields == [('field', '*', '*')]:
            jq_filter = '.'  
        else:
            selection = []
            for field_type, *field_data in fields:
                if field_type == 'field':
                    field, alias = field_data
                    if ' ' in field or not re.match(r'^[\w\.\[\]]+$', field):
                        safe_field = field.replace('"', '\\"')
                        selection.append(f'"{alias}": (."{safe_field}"? // null)')
                    else:
                        formatted_path = format_field_path(field)
                        selection.append(f'"{alias}": (.{formatted_path} // null)')
                elif field_type == 'aggregation':
                    func, field_path, alias = field_data
                    if func == 'count' and field_path == '*':
                        selection.append(f'"{alias}": (.{field_path}? | length)')
                    elif func == 'count':
                        if '.' in field_path:
                            array_field, value_field = field_path.rsplit('.', 1)
                            agg_expr = f'(.{array_field}? | map(select(. != null)) | length)'
                        else:
                            agg_expr = f'(.{field_path}? | map(select(. != null)) | length)'
                        selection.append(f'"{alias}": {agg_expr}')
                    else:
                        if '.' in field_path:
                            array_field, value_field = field_path.rsplit('.', 1)
                            mapped_values = f'.{array_field}? | map(.{value_field}?) | map(select(type == "number"))'
                            if func == 'sum':
                                agg_expr = f'({mapped_values} | add)'
                            elif func == 'avg':
                                agg_expr = f'({mapped_values} | add / length)'
                            else:
                                agg_expr = f'({mapped_values} | {func})'
                            selection.append(f'"{alias}": {agg_expr}')
                        else:
                            raise ValueError(f"Aggregation {func} requires a nested field path")
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