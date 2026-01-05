# High-Quality Code Specification – Simplicity, Readability, and Maintainability First

## Core Principles
- Prioritize **simplicity, readability, and maintainability** above all.
- Avoid premature abstraction, optimization, or over-engineering.
- Code should be understandable in ≤10 seconds; favor straightforward solutions over "clever" or "elegant" ones.

## Python Code Quality

### Readability
- Use precise, full-word variable and function names (use standard abbreviations only where conventional).
- Keep functions ≤50 lines with a single responsibility; name them as verbs.
- Avoid obscure tricks, excessive list/dict comprehensions, overuse of *args/**kwargs, or decorators.
- Break complex logic into small, well-named helper functions.

### Types (Mandatory)
- Always use full type annotations.
- Avoid `Any` except for dynamic JSON or unavoidable third-party interfaces.
- Prefer `dataclass`, `TypedDict`, `Protocol`, or `NewType` for structured data.

### Design
- Favor functional style with data classes; minimize deep inheritance hierarchies.
- Use composition over inheritance; employ ABCs or Protocols only when implementing multiple similar interfaces.
- No circular imports.
- Use dependency injection for configuration, logging, databases, etc.

### Errors & Resources
- Handle exceptions explicitly; never use bare `except:`.
- Use context managers for resource management.
- Validate all public inputs.

### Logging
- Use `info` level for key execution paths.
- Log exceptions at `error` level with relevant context.
- No `print()` statements for debugging.

### Testing
- Write unit tests for all core logic in the `tests/` directory; aim for ≥90% coverage.
- Name tests as `test_<feature>_<expected_behavior>`.
- Never modify production code without corresponding tests.

### Performance & Security
- Avoid unjustified O(n²) or worse algorithms in hot paths.
- Sanitize and validate all user input.
- Never hardcode secrets; load them from configuration or secret management systems.

### Formatting & Linting
- Ensure zero errors with `ruff`, `black`, and `pyright`.
- Sort imports: standard library → third-party → local.

## General Guidelines
- Use English only for comments, docstrings, log messages, and error strings.
- Fully understand the surrounding code and context before suggesting or making changes.
- Do not generate unnecessary documentation, examples, stubs, or bloated `__init__.py` files unless explicitly requested.