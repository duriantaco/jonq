# Contributing to jonq

Thanks for your interest in helping with jonq! Here's how you can contribute:

## Quick Start

1. Fork the repo
2. Clone your fork: `git clone https://github.com/duriantaco/jonq.git`
3. Install for development: `pip install -e ".[dev]"`
4. Install hooks: `pre-commit install --install-hooks`
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
- Run `pre-commit run --all-files` before pushing
- Follow PEP 8 basics
- Include docstrings for functions and classes

## Testing
Run `pytest` before submitting your changes.

## Documentation
Keep `README.md`, `USAGE.md`, `SYNTAX.md`, and the Sphinx docs in `docs/source/`
in sync when changing CLI behavior, query syntax, output formats, or the Python
API.

## Releases
Maintainers publish from GitHub Releases:

1. Update `pyproject.toml`, `jonq/constants.py`, and `CHANGELOG.md`
2. Open and merge the release prep PR
3. Create a GitHub Release for the version tag
4. The release workflow builds the package and publishes it to PyPI

PyPI publishing uses trusted publishing, so the PyPI project must allow this
repository and the `pypi` GitHub environment.

## Need Help?
Open an issue with your question!

Thanks for contributing!
