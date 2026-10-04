# Contributing to Discord orbshacker

Thank you for your interest in contributing to this project! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/DanielPires2000/orbshacker.git`
3. Install development dependencies: `pip install -r requirements-dev.txt`
4. Copy the settings template: `copy settings.example.py settings.py`
5. Create a new branch: `git checkout -b feature/add-new-game-support`
6. Make your changes
7. Run the checks: `python -m pytest` and `python -m ruff check .`
8. Commit your changes: `git commit -m "Add support for new game detection"`
9. Push to your fork: `git push origin feature/add-new-game-support`
10. Open a Pull Request

## Code Style

- Follow PEP 8 Python style guide (enforced by `ruff check .`)
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and single-purpose
- Comment complex logic, but avoid obvious comments
- Keep `orbshacker/timer.py`, `orbshacker/bake.py` and `orbshacker/janitor.py` stdlib-only (their source is inlined into faked scripts)

## Tests

- Add or update tests under `tests/` for every behavior change
- Run the full suite with `python -m pytest`
- Tests must not touch the network or the real Steam installation

## Commit Messages

- Use clear, descriptive commit messages
- Start with a capital letter
- Use imperative mood ("Add feature" not "Added feature")
- Reference issues when applicable

## Pull Request Process

1. Ensure `python -m pytest` and `python -m ruff check .` pass
2. Update documentation if needed
3. Test on Windows (the only supported platform)
4. Write a clear PR description explaining your changes

## Reporting Issues

When reporting issues, please include:
- Description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- System information (OS, Python version)
- Error messages if any

## Questions?

Feel free to open an issue for any questions or discussions about the project.

Thank you for contributing!

