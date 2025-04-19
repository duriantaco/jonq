import logging
from jonq.ast import *
from jonq.parser import parse_path, parse_condition_tokens
from jonq.generator import generate_jq_path, generate_jq_condition

logging.basicConfig(level=logging.INFO)

def transform_nested_array_path(field_path):
    """Transform a field path with array notation to JQ syntax"""
    path = parse_path(field_path)
    return generate_jq_path(path)

def build_jq_path(field_path):
    """Build a JQ path from a field reference"""
    path = parse_path(field_path)
    return generate_jq_path(path)

def format_field_path(field):
    """Format a field path for JQ"""
    path = parse_path(field)
    return generate_jq_path(path)

def parse_condition_for_from(tokens):
    """Parse condition tokens for FROM context"""
    condition = parse_condition_tokens(tokens)
    return generate_jq_condition(condition, "array") if condition else None

def escape_string(s):
    """Escape a string for jq"""
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        content = s[1:-1]
        escaped = content.replace('"', '\\"')
        return f'"{escaped}"'
    return s