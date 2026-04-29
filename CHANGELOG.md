# Changelog

## Unreleased

### Added
- **Raw scalar output**: `-r`, `--raw`, and `--raw-output` print selected scalar values without JSON quotes for shell pipelines.

## [v0.3.0] - 2026-03-22

### Added

#### Output & Display
- **Table output**: `--format table` or `-t` renders results as aligned terminal tables with headers and separators
- **YAML output**: `--format yaml` renders results as YAML (uses pyyaml if available, built-in fallback otherwise)
- **`--explain` mode**: shows parsed query breakdown (fields, conditions, grouping) and the generated jq filter
- **`--time` flag**: prints parse/execute/format timing to stderr
- **Auto-detect stdin**: `curl ... | jonq "select name"` works without needing `-` as source

#### Query Language
- **CASE/WHEN/THEN/ELSE/END**: conditional expressions — `select case when age > 30 then "senior" else "junior" end as level`
- **COALESCE**: null fallback with nested function support — `select coalesce(nickname, name) as display`
- **`||` operator**: SQL-standard string concatenation — `select first || ' ' || last as full_name`
- **IS NULL / IS NOT NULL**: null checks in conditions — `select * if email is not null`
- **Type casting**: `int()`, `float()`, `str()` / `string()`, `type()`
- **Date/time functions**: `todate()`, `fromdate()`, `date()`, `timestamp()` with null-safe execution
- **Utility functions**: `keys()`, `values()`, `trim()`, `ltrim()`, `rtrim()`, `tojson()`, `fromjson()`, `reverse()`, `sort()`, `unique()`, `flatten()`, `not_null()`, `to_entries()`, `from_entries()`

#### Terminal UX
- **Rich REPL**: readline with persistent history (`~/.jonq_history`) and tab completion for field names + keywords
- **`--follow` mode**: stream NDJSON from stdin line-by-line — `tail -f app.log | jonq --follow "select level, msg if level = 'error'"`
- **Shell completions**: `jonq --completions bash|zsh|fish` generates completion scripts

### Changed
- Version bump to 0.3.0
- Unified all function-name-to-jq-builtin mappings into a single `_FUNC_MAP` constant (eliminated 3 duplicate copies)
- Expression-only queries now properly map over array elements instead of wrapping the whole input
- Path-explorer schema preview now shows nested JSON paths like `orders[].price` instead of only shallow field listings
- Reuse bounded sync and async jq worker pools for repeated identical filters
- Main streaming execution path now chunks root-array JSON in memory instead of splitting to temp files
- Repositioned README/package metadata around JSON exploration and extraction

### Fixed
- Null-sensitive functions (`todate`, `tonumber`) are now guarded against null input instead of crashing
- Schema validator recognizes CASE expressions, `||` operator, and `coalesce` — no longer rejects them as unknown fields
- Sync jq runtime errors that only write to `stderr` no longer hang waiting on `stdout`
- Async jq workers are cleaned up with their event loop, preventing leftover subprocess transport warnings
- `--follow` mode skips empty results instead of printing `[]` for non-matching lines

## [v0.2.0] - 2026-03-08

### Added
- **DISTINCT**: `select distinct city` returns unique rows
- **COUNT DISTINCT**: `select count(distinct city) as n`
- **Standalone LIMIT**: `select * limit 10` (independent of sort)
- **IN operator**: `select * if city in ('New York', 'Chicago')`
- **NOT operator**: `select * if not age > 30`
- **LIKE operator**: `select * if name like 'Al%'` (supports `%` wildcard for startswith, endswith, contains)
- **String functions**: `upper()`, `lower()`, `length()`
- **Math functions**: `round()`, `abs()`, `ceil()`, `floor()`
- **Schema preview**: run `jonq data.json` with no query to inspect fields and types
- **Interactive REPL**: `jonq -i data.json` for interactive querying
- **Watch mode**: `--watch` flag to re-run query on file change
- **URL fetch**: `jonq https://api.example.com/data "select id"`
- **Multi-file glob**: `jonq 'logs/*.json' "select *"`
- **Auto-detect NDJSON**: no flag needed for newline-delimited JSON
- **Fuzzy field suggestions**: typo correction with Levenshtein distance
- **Colorized output**: syntax-highlighted JSON when outputting to terminal
- **`python -m jonq`**: added `__main__.py` entry point
- **Constants module**: centralized all magic numbers and ANSI codes

### Fixed
- Dynamic HAVING field mappings instead of hardcoded alias dict
- Removed inline jq comments (`# sum`) from generated filters
- `from` clause now correctly iterates arrays (`.path[]` instead of `.path`)
- Schema validator recognizes `sort`, `distinct`, `as`, arithmetic operators
- Schema validator skips validation when `from` clause is used
- Logging level changed from INFO to WARNING (no more filter spam)

### Changed
- Version bump to 0.2.0
- Replaced all star imports with explicit imports
- Replaced all hardcoded ANSI codes with `_Colors` class
- Replaced all magic numbers with named constants
- Removed dead code: `handle_error`, `extract_value_from_quotes`, `_AGG_FUNCTIONS`, `parse_condition` (jq_filter.py), `use_fast` parameter
- Executor raises `ValueError` instead of `RuntimeError` for jq errors
- Updated all Sphinx docs, README, and SYNTAX.md

## [v0.1.1] - 2025-08-22

### Added

- NDJSON input mode: --ndjson (supports - stdin). Lines are wrapped into a JSON array for querying. Currently incompatible with `--stream`.. prints a friendly message if combined

### Fixed

- Properly await aclose()/close() to eliminate RuntimeWarning: coroutine ... was never awaited etc etc.
- Schema validation now allows nested paths (e.g., items[].price) by validating only the top level head
- Better handling of comparisons (`== != >= <= > <`), numbers (ints/floats), and `contains`

### Changed

- CSV pipeline. Convert JSON -> CSV before applying `--limit`
- Pretty printing applies only to JSON output

## [v0.1.0] - 2025-06-22

### Added
- Concurrent chunk processing for 2-5x performance improvement on large files
- Prevents freezing on large datasets
- New `run_jq_async()` and `run_jq_streaming_async()` functions for concurrent processing
- Streaming mode now processes chunks in parallel

### Improved  
- Tool remains responsive during large file processing

### Technical
- Added `aiofiles` dependency for async file operations
- Internal async architecture for streaming operations

## [v0.0.1]  
- Prototype implementation
- Initial public release
- SQL-like query syntax for JSON files
- Support for field selection, filtering, sorting, and limiting results
- Support for aggregation functions (sum, avg, count, max, min)
- Support for nested JSON traversal with dot notation
- Support for array indexing with [n] syntax
- Support for complex boolean expressions with AND, OR, and parentheses
- Support for grouping and aggregation with GROUP BY
- Support for handling special characters in field names
- Comprehensive test suite
