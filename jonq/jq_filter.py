import logging
from jonq.generator import generate_jq_filter as ast_generate_jq_filter
from jonq.generator import format_field_path as ast_format_field_path
from jonq.generator import build_jq_path as ast_build_jq_path
from jonq.generator import transform_nested_array_path as ast_transform_nested_array_path
from jonq.generator import escape_string as ast_escape_string
from jonq.parser import parse_condition_tokens

logging.basicConfig(level=logging.INFO)

def format_field_path(field):
    return ast_format_field_path(field)

def build_jq_path(field_path):
    return ast_build_jq_path(field_path)

def transform_nested_array_path(field_path):
    return ast_transform_nested_array_path(field_path)

def escape_string(s):
    return ast_escape_string(s)

def parse_condition(tokens, from_path=None):
    if from_path and '[]' in from_path:
        context = "array"
    else:
        context = "root"
        
    condition = parse_condition_tokens(tokens)
    if condition:
        from jonq.generator import generate_jq_condition
        return generate_jq_condition(condition, context)
    return None

def generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path=None):
    return ast_generate_jq_filter(
        fields, condition, group_by, having, order_by, sort_direction, limit, from_path
    )