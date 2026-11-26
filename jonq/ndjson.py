from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from decimal import Decimal, InvalidOperation
import json


class EventReader:
    """Read NDJSON objects and count rejected lines as they are reported."""

    def __init__(
        self,
        lines: Iterable[bytes],
        report_error: Callable[[int, str], None],
        *,
        parse_float: Callable[[str], float | Decimal] = float,
    ):
        self.lines = lines
        self.report_error = report_error
        self.parse_float = parse_float
        self.invalid_lines = 0

    def reject(self, line_no: int, message: str) -> None:
        self.invalid_lines += 1
        self.report_error(line_no, message)

    def __iter__(self) -> Iterator[tuple[int, dict]]:
        for line_no, raw_line in enumerate(self.lines, start=1):
            if not raw_line.strip(b" \t\r\n"):
                continue
            try:
                event = json.loads(
                    raw_line.decode("utf-8"),
                    parse_float=self.parse_float,
                    parse_constant=_reject_json_constant,
                )
                if not isinstance(event, dict):
                    raise ValueError("expected a JSON object")
            except UnicodeDecodeError:
                self.reject(line_no, "invalid UTF-8")
            except json.JSONDecodeError as exc:
                self.reject(line_no, f"invalid JSON at column {exc.colno}: {exc.msg}")
            except RecursionError:
                self.reject(line_no, "JSON nesting is too deep")
            except InvalidOperation:
                self.reject(line_no, "invalid JSON number")
            except ValueError as exc:
                self.reject(line_no, str(exc))
            else:
                yield line_no, event


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number {value}")
