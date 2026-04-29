# Contributing to jonq

Thanks for your interest in helping with jonq! Here's how you can contribute:

## Quick Start

1. Fork the repo
2. Clone your fork: `git clone https://github.com/duriantaco/jonq.git`
3. Install for development: `pip install -e .`
4. Install test dependencies: `pip install pytest pytest-asyncio`
5. Install docs dependencies when editing docs: `pip install -r docs/requirements.txt`

## How to Contribute

### Reporting Bugs
- Check if the bug is already reported
- Include clear steps to reproduce
- Mention your environment (Python version, OS)

### Submitting Changes
1. Create a branch: `git switch -c fix-something`
2. Make your changes
3. Run tests: `pytest`
4. Build docs when documentation changed: `python -m sphinx -b html docs/source /tmp/jonq-docs`
5. Commit with a clear message
6. Push to your fork
7. Open a pull request

### Code Style
- Follow PEP 8 basics
- Include docstrings for functions and classes

## Testing
Run `pytest` before submitting your changes.

## Documentation
Keep `README.md`, `USAGE.md`, `SYNTAX.md`, and the Sphinx docs in `docs/source/`
in sync when changing CLI behavior, query syntax, output formats, or the Python
API.

## Need Help?
Open an issue with your question!

Thanks for contributing!
