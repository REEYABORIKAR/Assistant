---
name: coding-standards
description: Universal, language-agnostic coding standards, best practices, and software engineering patterns. Use when writing code, reviewing code, or establishing project conventions. Covers readability, KISS, DRY, YAGNI, naming, functions, error handling, testing, and architecture.
---

# Coding Standards & Best Practices

Universal coding standards applicable across programming languages, frameworks, and projects.

## Code Quality Principles

### 1. Readability First

Code is read far more often than it is written.

- Use clear variable, function, class, and module names.
- Prefer straightforward code over clever code.
- Keep formatting consistent.
- Make intent obvious.
- Prefer self-documenting code over unnecessary comments.
- Follow the conventions of the language and ecosystem being used.

```python
# GOOD: Intent is obvious
market_search_query = "election"
is_user_authenticated = True
total_revenue = 1000

# BAD: Meaning must be guessed
q = "election"
flag = True
x = 1000
```

### 2. KISS: Keep It Simple

Use the simplest solution that correctly solves the problem.

- Avoid unnecessary abstractions.
- Avoid premature optimization.
- Don't introduce infrastructure without a concrete need.
- Prefer understandable code over clever tricks.
- Optimize only after identifying an actual bottleneck.

### 3. DRY: Don't Repeat Yourself

Avoid duplicating knowledge or business logic.

- Extract repeated logic into reusable functions or modules.
- Centralize shared validation and configuration.
- Reuse abstractions when they represent the same concept.
- Do not create abstractions merely because two pieces of code happen to look similar.

DRY does not mean eliminating every repeated line. Sometimes a small amount of duplication is clearer than a bad abstraction.

### 4. YAGNI: You Aren't Gonna Need It

Do not build functionality based on hypothetical future requirements.

- Implement what is currently required.
- Avoid speculative abstractions.
- Avoid unused configuration options.
- Avoid unnecessary extensibility.
- Refactor when real requirements emerge.

## Naming Standards

Names should describe intent rather than implementation details.

### Variables

Use nouns or descriptive noun phrases.

```python
# GOOD
market_search_query = "election"
active_users = []
retry_count = 0
is_authenticated = True

# BAD
q = "election"
arr = []
x = 0
flag = True
```

### Functions

Functions should usually describe an action. Prefer verb-based names.

```python
# GOOD
def fetch_market_data(): ...
def calculate_similarity(): ...
def validate_email(): ...
def save_user(): ...

# BAD
def market(): ...
def similarity(): ...
def thing(): ...
```

Boolean functions should read naturally.

```python
def is_valid_email(email: str) -> bool: ...
def has_permission(user, resource) -> bool: ...
def can_delete_post(user, post) -> bool: ...
```

### Classes

Classes should generally represent concepts or entities and use noun-based names.

```python
class UserRepository: ...
class PaymentService: ...
class Market: ...
```

Avoid meaningless names like `Manager`, `Helper`, `Processor` unless the surrounding domain makes their responsibility unambiguous.

## Functions

### Keep Functions Focused

A function should perform one coherent task.

```python
# BAD
def process_user(user):
    validate_user(user)
    save_user(user)
    send_email(user)
    generate_report(user)
    update_analytics(user)

# BETTER
def register_user(user):
    validate_user(user)
    save_user(user)
    send_welcome_email(user)
```

### Prefer Explicit Inputs and Outputs

Avoid functions that secretly depend on unrelated global state.

```python
# BAD
current_tax_rate = 0.18
def calculate_price(price):
    return price * (1 + current_tax_rate)

# GOOD
def calculate_price(price: float, tax_rate: float) -> float:
    return price * (1 + tax_rate)
```

### Avoid Excessive Parameters

Large parameter lists often indicate that related data should be grouped.

```python
from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str
    age: int

def create_user(user: User): ...
```

## Error Handling

### Catch Specific Errors

```python
# GOOD
try:
    user = repository.get_user(user_id)
except UserNotFoundError:
    return None

# BAD
try:
    user = repository.get_user(user_id)
except Exception:
    pass
```

### Preserve Useful Context

```python
def load_config(path: str) -> dict:
    try:
        with open(path, "r") as file:
            return parse_config(file.read())
    except OSError as error:
        raise RuntimeError(
            f"Failed to load configuration from {path}"
        ) from error
```

Errors should answer:
- What failed?
- Where did it fail?
- What operation was being attempted?

### Fail Fast

Validate assumptions near system boundaries.

```python
def create_user(email: str, age: int):
    if not email:
        raise ValueError("Email is required")
    if age < 0:
        raise ValueError("Age cannot be negative")
```

## Type Safety

Use the strongest practical type guarantees available in the language.

```python
# BAD
def get_market(market_id): ...

# BETTER
def get_market(market_id: str) -> Market: ...
```

## Testing Standards

### AAA Pattern

1. Arrange
2. Act
3. Assert

```python
def test_calculates_similarity_correctly():
    vector_a = [1, 0, 0]
    vector_b = [0, 1, 0]
    similarity = calculate_cosine_similarity(vector_a, vector_b)
    assert similarity == 0
```

### Test Naming

Test names should describe expected behavior.

```python
def test_returns_empty_list_when_no_markets_match(): ...
def test_rejects_invalid_email_address(): ...
def test_raises_error_when_database_is_unavailable(): ...
```

## General Rule

Prefer code that is:

1. Correct
2. Clear
3. Maintainable
4. Testable
5. Secure
6. Efficient

In that order unless the project's requirements explicitly demand otherwise.

Good code should make the next developer's job easier. That developer may be someone else. More often than anyone would like to admit, it will be you six months later wondering who wrote this disaster.
