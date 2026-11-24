# Contributing to AmendAQ

Thank you for your interest in contributing to AmendAQ!

## Development Setup

AmendAQ uses `uv` for Python dependency management and npm for the frontend.

```bash
# Install dependencies
uv sync --extra dev --extra web

# Start the development environment (backend + frontend)
scripts/restart-dev.sh

# Stop the development environment
scripts/stop-dev.sh
```

The script starts:
- FastAPI backend on port 8765 (default)
- Vite frontend on port 5180 (default)

## Running Tests

```bash
uv run pytest
```

## Code Style

- Python code follows standard Python conventions
- Keep changes focused and atomic
- Write clear commit messages

## Reporting Issues

If you encounter issues:

1. Check existing issues first
2. For bugs, include:
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant trace files from `data/traces/` (AmendAQ logs full execution traces there)
   - Your environment (OS, Python version, model provider)

3. For questions about the product or usage, use the Question issue template

## Pull Requests

- Fork the repository
- Create a feature branch
- Make your changes
- Ensure tests pass
- Submit a PR with a clear description

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
