---

name: coding-standards
description: Universal, language-agnostic coding standards, best practices, and software engineering patterns. Examples use Python for clarity.
author: affaan-m
version: "2.0"
--------------

# Coding Standards & Best Practices

Universal coding standards applicable across programming languages, frameworks, and projects.

Python is used for examples, but the underlying principles should be applied regardless of the language or technology stack.

## Code Quality Principles

### 1. Readability First

Code is read far more often than it is written.

* Use clear variable, function, class, and module names.
* Prefer straightforward code over clever code.
* Keep formatting consistent.
* Make intent obvious.
* Prefer self-documenting code over unnecessary comments.
* Follow the conventions of the language and ecosystem being used.

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

---

### 2. KISS: Keep It Simple

Use the simplest solution that correctly solves the problem.

* Avoid unnecessary abstractions.
* Avoid premature optimization.
* Don't introduce infrastructure without a concrete need.
* Prefer understandable code over clever tricks.
* Optimize only after identifying an actual bottleneck.

```python
# GOOD
def calculate_total(prices: list[float]) -> float:
    return sum(prices)


# BAD: Unnecessary abstraction for a simple operation
class PriceAggregationEngine:
    def execute_aggregation_pipeline(self, prices):
        total = 0

        for price in prices:
            total += price

        return total
```

---

### 3. DRY: Don't Repeat Yourself

Avoid duplicating knowledge or business logic.

* Extract repeated logic into reusable functions or modules.
* Centralize shared validation and configuration.
* Reuse abstractions when they represent the same concept.
* Do not create abstractions merely because two pieces of code happen to look similar.

```python
# BAD
user_email = user.email.strip().lower()
admin_email = admin.email.strip().lower()


# GOOD
def normalize_email(email: str) -> str:
    return email.strip().lower()


user_email = normalize_email(user.email)
admin_email = normalize_email(admin.email)
```

DRY does not mean eliminating every repeated line.

Sometimes a small amount of duplication is clearer than a bad abstraction.

---

### 4. YAGNI: You Aren't Gonna Need It

Do not build functionality based on hypothetical future requirements.

* Implement what is currently required.
* Avoid speculative abstractions.
* Avoid unused configuration options.
* Avoid unnecessary extensibility.
* Refactor when real requirements emerge.

Build for known requirements, not imaginary future ones.

---

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

Short names are acceptable when their meaning is universally obvious within a tiny scope.

```python
for i in range(10):
    print(i)
```

---

### Functions

Functions should usually describe an action.

Prefer verb-based names.

```python
# GOOD
def fetch_market_data():
    ...


def calculate_similarity():
    ...


def validate_email():
    ...


def save_user():
    ...


# BAD
def market():
    ...


def similarity():
    ...


def thing():
    ...
```

Boolean functions should read naturally.

```python
def is_valid_email(email: str) -> bool:
    ...


def has_permission(user, resource) -> bool:
    ...


def can_delete_post(user, post) -> bool:
    ...
```

---

### Classes

Classes should generally represent concepts or entities and use noun-based names.

```python
class UserRepository:
    ...


class PaymentService:
    ...


class Market:
    ...
```

Avoid meaningless names such as:

```python
class Manager:
    ...

class Helper:
    ...

class Processor:
    ...
```

unless the surrounding domain makes their responsibility unambiguous.

---

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

If a function requires extensive explanation to describe what it does, it probably has too many responsibilities.

---

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

Explicit dependencies make code easier to understand, test, and reuse.

---

### Avoid Excessive Parameters

Large parameter lists often indicate that related data should be grouped.

```python
from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str
    age: int


def create_user(user: User):
    ...
```

Prefer meaningful domain objects over passing many loosely related arguments.

---

## Data and State

### Minimize Shared Mutable State

Mutation is sometimes necessary, but uncontrolled shared mutation makes systems difficult to reason about.

Prefer returning new values when practical.

```python
# GOOD
def rename_user(user: dict, new_name: str) -> dict:
    return {
        **user,
        "name": new_name,
    }
```

When mutation is appropriate, keep its scope small and obvious.

```python
items.append(new_item)
```

Mutation itself is not inherently bad.

Hidden or widely shared mutation is.

---

### Use Appropriate Data Structures

Choose data structures based on their intended behavior.

```python
# List: ordered collection
users = ["alice", "bob"]

# Set: unique membership
permissions = {"read", "write"}

# Dictionary: key-value lookup
users_by_id = {
    1: "alice",
    2: "bob",
}
```

Do not use one structure for everything merely because it is familiar.

---

## Type Safety

Use the strongest practical type guarantees available in the language.

In Python, use type hints for public interfaces and important internal boundaries.

```python
from dataclasses import dataclass


@dataclass
class Market:
    id: str
    name: str
    status: str


def get_market(market_id: str) -> Market:
    ...
```

Avoid vague types when a meaningful type can be expressed.

```python
# BAD
def get_market(market_id):
    ...


# BETTER
def get_market(market_id: str) -> Market:
    ...
```

Type systems and static analysis should help catch mistakes before runtime.

They should not be used to create unnecessary complexity.

---

## Error Handling

Errors should fail predictably and provide useful context.

### Catch Specific Errors

```python
# GOOD
try:
    user = repository.get_user(user_id)
except UserNotFoundError:
    return None
```

Avoid catching everything unless you are at a deliberate application boundary.

```python
# BAD
try:
    user = repository.get_user(user_id)
except Exception:
    pass
```

Never silently swallow errors unless ignoring the failure is explicitly intended.

---

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

* What failed?
* Where did it fail?
* What operation was being attempted?

Do not expose sensitive internal information to end users.

---

### Fail Fast

Validate assumptions near system boundaries.

```python
def create_user(email: str, age: int):
    if not email:
        raise ValueError("Email is required")

    if age < 0:
        raise ValueError("Age cannot be negative")

    ...
```

Invalid data should not travel deep into the system before being rejected.

---

## Asynchronous Programming

Use asynchronous execution for operations that spend significant time waiting, such as:

* Network requests
* Database operations
* File I/O
* External APIs

```python
import asyncio


async def load_dashboard():
    users, markets, stats = await asyncio.gather(
        fetch_users(),
        fetch_markets(),
        fetch_stats(),
    )

    return users, markets, stats
```

Avoid unnecessary sequential execution.

```python
# BAD when operations are independent
users = await fetch_users()
markets = await fetch_markets()
stats = await fetch_stats()
```

Do not use asynchronous programming merely because the language supports it.

CPU-heavy operations usually require different concurrency strategies.

---

## Resource Management

Resources should always be released correctly.

This includes:

* Files
* Database connections
* Locks
* Network sockets
* Transactions
* Temporary resources

Use the language's resource-management mechanism.

```python
with open("data.txt", "r") as file:
    contents = file.read()
```

Prefer deterministic cleanup over relying on garbage collection.

---

## API Design Standards

APIs should be predictable, consistent, and boring.

Boring APIs are good APIs.

### REST Conventions

```text
GET    /api/markets
GET    /api/markets/{id}
POST   /api/markets
PUT    /api/markets/{id}
PATCH  /api/markets/{id}
DELETE /api/markets/{id}
```

Filtering and pagination:

```text
GET /api/markets?status=active&limit=10&offset=0
```

Follow the conventions of the API architecture being used.

Do not force REST conventions onto systems using RPC, GraphQL, messaging, or another architecture.

---

### Consistent Responses

```python
{
    "success": True,
    "data": markets,
    "meta": {
        "total": 100,
        "page": 1,
        "limit": 10,
    },
}
```

Error example:

```python
{
    "success": False,
    "error": {
        "code": "INVALID_REQUEST",
        "message": "Invalid request",
    },
}
```

Clients should not need to guess the shape of responses.

---

## Input Validation

Never trust data entering the system.

Validate inputs from:

* Users
* HTTP requests
* Files
* Databases
* External APIs
* Message queues
* Environment variables
* Configuration files

Example using a validation model:

```python
from pydantic import BaseModel, Field


class CreateMarketRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    categories: list[str]
```

Validation should occur near the boundary where untrusted data enters the application.

---

## Architecture and Separation of Concerns

Keep unrelated responsibilities separate.

A typical application might contain:

```text
src/
├── api/
├── domain/
├── services/
├── repositories/
├── models/
├── schemas/
├── utils/
├── config/
└── tests/
```

The exact directory names do not matter.

The important part is maintaining clear responsibility boundaries.

For example:

```text
API layer
    ↓
Service / business logic
    ↓
Repository / data access
    ↓
Database
```

Avoid placing business logic directly inside:

* Controllers
* Routes
* UI components
* Database models
* Framework callbacks

Framework code should usually coordinate domain logic rather than contain all of it.

---

## Dependency Direction

Higher-level business logic should avoid unnecessary dependence on implementation details.

```python
from typing import Protocol


class UserRepository(Protocol):
    def get_user(self, user_id: str):
        ...


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository
```

This allows infrastructure implementations to change without rewriting core business logic.

Do not introduce interfaces or dependency injection everywhere.

Use them where multiple implementations, testing, or architectural boundaries justify them.

---

## File Organization

Organize files by responsibility or domain.

Avoid:

```text
utils/
├── everything.py
└── helpers.py
```

Prefer meaningful modules:

```text
users/
├── models.py
├── service.py
├── repository.py
└── schemas.py
```

For larger systems, feature-based organization is often easier to scale than organizing everything purely by technical type.

---

## Comments & Documentation

### Explain Why, Not What

```python
# GOOD
# Retry with exponential backoff to avoid overwhelming
# the service during temporary outages.
delay = min(2 ** retry_count, 30)
```

Avoid comments that merely translate code into English.

```python
# BAD
# Increment retry count
retry_count += 1
```

If code requires a comment to explain what it does, first consider whether the code itself can be made clearer.

---

### Document Public Interfaces

Use the standard documentation convention of the language.

Python example:

```python
def search_markets(query: str, limit: int = 10) -> list[Market]:
    """
    Search markets using semantic similarity.

    Args:
        query: Natural-language search query.
        limit: Maximum number of results.

    Returns:
        Markets sorted by similarity.

    Raises:
        SearchError: If the search backend fails.
    """
    ...
```

Document:

* Public APIs
* Important assumptions
* Non-obvious behavior
* Side effects
* Exceptions
* Constraints

Avoid documentation that merely duplicates the implementation.

---

## Database Best Practices

### Retrieve Only What You Need

```sql
SELECT id, name, status
FROM markets
LIMIT 10;
```

Avoid:

```sql
SELECT *
FROM markets;
```

when only a few columns are required.

---

### Parameterize Queries

Never construct SQL using untrusted string interpolation.

```python
# BAD
query = f"SELECT * FROM users WHERE email = '{email}'"
```

Use parameterized queries or a trusted query builder/ORM.

```python
cursor.execute(
    "SELECT id, email FROM users WHERE email = %s",
    (email,),
)
```

---

### Avoid N+1 Queries

Do not repeatedly query related data when it can be retrieved efficiently in fewer operations.

Understand how your ORM or database abstraction executes queries.

Convenient code can still produce terrible SQL.

---

### Use Transactions for Atomic Operations

Operations that must succeed or fail together belong in a transaction.

```python
with database.transaction():
    create_order(order)
    reserve_inventory(order)
    record_payment(order)
```

Partial success should not leave the system in an invalid state.

---

## Performance Best Practices

### Measure Before Optimizing

Do not optimize based on intuition alone.

Use:

* Profilers
* Benchmarks
* Metrics
* Query analysis
* Tracing

Find the actual bottleneck first.

---

### Cache Expensive Work Carefully

```python
from functools import lru_cache


@lru_cache(maxsize=128)
def calculate_expensive_result(value: int):
    ...
```

Caching introduces its own problems:

* Stale data
* Memory usage
* Invalidation
* Consistency

Do not cache something simply because caching exists.

---

### Avoid Unnecessary Work

```python
# GOOD
active_users = [
    user
    for user in users
    if user.is_active
]
```

Avoid repeatedly performing expensive operations inside loops when the result can be computed once.

---

## Logging

Use structured, meaningful logs.

```python
logger.info(
    "User created",
    extra={
        "user_id": user.id,
        "source": "registration",
    },
)
```

Avoid meaningless logs:

```python
print("here")
print("worked")
print("error")
```

Never log:

* Passwords
* Authentication tokens
* API secrets
* Private keys
* Sensitive personal information

Logs are operational data, not a dumping ground for everything in memory.

---

## Configuration and Secrets

Configuration should be separate from application logic.

```python
import os

database_url = os.environ["DATABASE_URL"]
```

Never hardcode secrets.

```python
# NEVER
API_KEY = "super-secret-production-key"
```

Secrets belong in appropriate secret-management systems or environment configuration.

---

## Security Principles

Security should be considered throughout development rather than added at the end.

Always consider:

* Input validation
* Authentication
* Authorization
* Injection attacks
* Secret management
* Dependency vulnerabilities
* Data exposure
* Rate limiting
* Secure defaults

Authentication answers:

> Who are you?

Authorization answers:

> Are you allowed to do this?

Do not confuse the two.

---

## Testing Standards

Tests should verify behavior rather than implementation details.

### AAA Pattern

Structure tests using:

1. Arrange
2. Act
3. Assert

```python
def test_calculates_similarity_correctly():
    # Arrange
    vector_a = [1, 0, 0]
    vector_b = [0, 1, 0]

    # Act
    similarity = calculate_cosine_similarity(
        vector_a,
        vector_b,
    )

    # Assert
    assert similarity == 0
```

---

### Test Naming

Test names should describe expected behavior.

```python
def test_returns_empty_list_when_no_markets_match():
    ...


def test_rejects_invalid_email_address():
    ...


def test_raises_error_when_database_is_unavailable():
    ...
```

Avoid:

```python
def test_works():
    ...


def test_function():
    ...
```

A failed test should tell the developer what behavior broke.

---

### Test Important Boundaries

Prioritize tests for:

* Business logic
* Validation
* Error handling
* Security rules
* Data transformations
* External integration boundaries
* Important edge cases

Do not chase coverage percentages at the expense of meaningful tests.

100% coverage does not guarantee correct software.

---

## Code Smell Detection

Watch for common anti-patterns.

### 1. Long Functions

```python
# BAD
def process_market_data():
    # 100+ lines
    ...
```

Prefer focused operations:

```python
def process_market_data(data):
    validated = validate_market_data(data)
    transformed = transform_market_data(validated)
    return save_market_data(transformed)
```

Function length alone is not the issue.

Too many responsibilities are.

---

### 2. Deep Nesting

```python
# BAD
if user:
    if user.is_admin:
        if market:
            if market.is_active:
                if has_permission:
                    delete_market()
```

Prefer guard clauses:

```python
if not user:
    return

if not user.is_admin:
    return

if not market:
    return

if not market.is_active:
    return

if not has_permission:
    return

delete_market()
```

---

### 3. Magic Values

```python
# BAD
if retry_count > 3:
    ...

time.sleep(5)
```

Prefer named constants:

```python
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

if retry_count > MAX_RETRIES:
    ...

time.sleep(RETRY_DELAY_SECONDS)
```

Named constants communicate intent and centralize configuration.

---

### 4. Boolean Blindness

Calls containing several raw booleans are difficult to understand.

```python
# BAD
create_user("alice", True, False, True)
```

Prefer named arguments or meaningful types.

```python
create_user(
    username="alice",
    is_admin=True,
    send_welcome_email=False,
    is_active=True,
)
```

---

### 5. God Objects

Avoid classes or modules responsible for everything.

```text
ApplicationManager
├── authentication
├── database
├── email
├── payments
├── analytics
├── logging
├── caching
└── reporting
```

Split responsibilities into focused modules or services.

---

### 6. Premature Abstraction

Do not build elaborate abstractions before understanding the actual pattern.

Three similar lines of code can be better than a framework designed to eliminate them.

Abstract when the shared concept is understood.

---

### 7. Hidden Side Effects

Functions should not unexpectedly modify unrelated state.

```python
# BAD
def calculate_total(order):
    order.status = "processed"
    send_notification(order.user)

    return sum(item.price for item in order.items)
```

A function named `calculate_total` should calculate a total.

Side effects should be explicit in naming and architecture.

---

## Dependency Management

Keep dependencies intentional.

Before adding a dependency, consider:

* Is it actively maintained?
* Is it secure?
* Is the functionality difficult to implement safely?
* What is its maintenance cost?
* How much complexity does it introduce?
* Is it actually necessary?

Do not install a library to avoid writing five obvious lines of code.

Do not reimplement complex security, cryptography, parsing, or protocol logic merely to avoid a dependency.

---

## Version Control

Commits should represent coherent changes.

Good commit messages describe intent:

```text
feat: add market search endpoint
fix: prevent duplicate user registration
refactor: separate payment validation
test: add authentication edge cases
```

Avoid:

```text
update
changes
fix stuff
final
final-final
final-final-2
```

The repository is a historical record, not an archaeological punishment for future developers.

---

## General Rule

Prefer code that is:

1. Correct
2. Clear
3. Maintainable
4. Testable
5. Secure
6. Efficient

In that order unless the project's requirements explicitly demand otherwise.

Do not sacrifice clarity for theoretical performance.

Do not sacrifice correctness for convenience.

Do not introduce complexity without a concrete benefit.

## Final Principle

Good code should make the next developer's job easier.

That developer may be someone else.

More often than anyone would like to admit, it will be you six months later wondering who wrote this disaster.
