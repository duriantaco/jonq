from __future__ import annotations

VERSION = "0.3.2"
USER_AGENT = f"jonq/{VERSION}"


class _Colors:
    """ANSI escape codes. All empty strings when stdout is not a TTY."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def _code(self, code: str) -> str:
        return code if self._enabled else ""

    @property
    def BOLD(self) -> str:
        return self._code("\033[1m")

    @property
    def DIM(self) -> str:
        return self._code("\033[2m")

    @property
    def RED(self) -> str:
        return self._code("\033[0;31m")

    @property
    def GREEN(self) -> str:
        return self._code("\033[32m")

    @property
    def YELLOW(self) -> str:
        return self._code("\033[33m")

    @property
    def CYAN(self) -> str:
        return self._code("\033[36m")

    @property
    def MAGENTA(self) -> str:
        return self._code("\033[35m")

    @property
    def BOLD_YELLOW(self) -> str:
        return self._code("\033[1;33m")

    @property
    def NC(self) -> str:
        return self._code("\033[0m")

    @property
    def CLEAR_SCREEN(self) -> str:
        return self._code("\033[2J\033[H")


URL_FETCH_TIMEOUT = 30  # seconds
WATCH_POLL_INTERVAL = 0.5  # seconds
WATCH_RETRY_INTERVAL = 1.0  # seconds on OS error
NDJSON_SNIFF_LINES = 10  # how many lines to check
NDJSON_MIN_VALID = 2  # minimum valid JSON lines to consider it NDJSON
SCHEMA_SAMPLE_TRUNCATE = 500  # max chars for sample JSON display
SCHEMA_PATH_SAMPLE_ROWS = 25  # sample this many array items for path exploration
SCHEMA_PATH_MAX_DEPTH = 5  # max nested depth to display in schema preview
SCHEMA_PATH_PREVIEW_ITEMS = 3  # preview this many scalar array values
ERROR_SAMPLE_SIZE = 1024 * 1024  # 1 MB sample for schema validation
FUZZY_MAX_DISTANCE = 3  # max edit distance for suggestions
FUZZY_MAX_RESULTS = 3  # max number of suggestions to show
WORKER_CACHE_SIZE = 32
