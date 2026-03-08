"""jonq - Human-readable syntax for jq"""

from .constants import VERSION as __version__  # noqa: F401 — single source of truth

__author__ = "oha"
__email__ = "aaronoh2015@gmail.com"

from .executor import run_jq, run_jq_async, run_jq_streaming, run_jq_streaming_async
from .query_parser import tokenize_query, parse_query
from .jq_filter import generate_jq_filter

__all__ = [
    "run_jq",
    "run_jq_async",
    "run_jq_streaming",
    "run_jq_streaming_async",
    "tokenize_query",
    "parse_query",
    "generate_jq_filter",
]
