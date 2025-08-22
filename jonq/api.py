import logging
from jonq.ast import *
from jonq.parser import parse_path, parse_condition_tokens
from jonq.generator import generate_jq_path, generate_jq_condition

logging.basicConfig(level=logging.INFO)

def transform_nested_array_path(field_path):
    path = parse_path(field_path)
    return generate_jq_path(path)

def build_jq_path(field_path):
    path = parse_path(field_path)
    return generate_jq_path(path)

def format_field_path(field):
    path = parse_path(field)
    return generate_jq_path(path)

def parse_condition_for_from(tokens):
    condition = parse_condition_tokens(tokens)
    return generate_jq_condition(condition, "array") if condition else None

def escape_string(s):
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        content = s[1:-1]
        escaped = content.replace('"', '\\"')
        return f'"{escaped}"'
    return s