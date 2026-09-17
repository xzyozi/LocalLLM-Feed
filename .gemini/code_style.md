# Project Rules & Coding Standards

You must follow these rules strictly when generating, editing, or refactoring code.

## 1. Python Guidelines (Ruff & Modern Python)
- **Static Analysis & Formatting**:
  - Code must pass **Ruff** checks.
  - Use **Ruff** (or Black-compatible) formatting style.
  - **Import Sorting**: Imports must be sorted alphabetically and organized into sections (Standard Library, Third Party, Local Application).
- **Type Hinting & Modern Syntax**:
  - **MANDATORY**: All function arguments, return values, and class attributes must have type hints.
  - Use modern type hinting syntax (e.g., `list[str]` instead of `List[str]` for Python 3.9+).
  - Prefer `pathlib` over `os.path`.
  - Use **f-strings** for string formatting.
- **Documentation (Google Style)**:
  - Add a **Google Style** docstring to every function and class.
  - Must include `Args:`, `Returns:`, and `Raises:` sections where applicable.
- **Error Handling**:
  - Never use bare `except:` clauses. Catch specific exceptions.
  - Use custom exception classes for domain-specific errors.

## 2. JavaScript Guidelines
- **Modern JS (ES6+)**:
  - Use `const` by default; use `let` only when reassignment is necessary. Never use `var`.
  - Use **Arrow Functions** where appropriate.
  - Prefer `async/await` over raw Promises/callbacks.
- **Naming**:
  - Variables/Functions: **camelCase** (e.g., `fetchUserData`).
  - Classes/Components: **PascalCase** (e.g., `UserProfile`).
  - Constants: **UPPER_SNAKE_CASE** (e.g., `MAX_RETRY_COUNT`).

## 3. File Naming Conventions
- **Python**: `snake_case.py` (e.g., `data_processor.py`)
  - Test files: `test_snake_case.py`
- **JavaScript**: `camelCase.js` (e.g., `apiClient.js`)

## 4. Code Quality & Architecture
- **DRY Principle**: Don't Repeat Yourself. Extract duplicate logic into helper functions.
- **Single Responsibility**: Functions should do one thing well. Keep them small.
- **Comments**: Do not state the obvious (e.g., "Increment i"). Explain *why*, not *what*.