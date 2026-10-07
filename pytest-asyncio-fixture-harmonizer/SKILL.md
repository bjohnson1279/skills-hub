---
name: pytest-asyncio-fixture-harmonizer
description: Diagnoses and repairs pytest-asyncio fixture setup errors, async/sync generator mismatches, missing pytest.ini asyncio_mode settings, and adds graceful offline server skip guards to E2E/conformance test suites.
---

# Pytest Asyncio Fixture Harmonizer

This skill provides diagnostic procedures and automated repair strategies for resolving `pytest-asyncio` fixture setup failures, async generator mismatches, and connection errors in Python E2E and cross-backend conformance test suites.

---

## Diagnostic Indicators

Activate this skill when encountering pytest setup errors such as:
1. `'test_name' requested an async fixture 'fixture_name', with no plugin or hook that handled it. This is an error, as pytest does not natively support it.`
2. `AssertionError` in `pytest_asyncio/plugin.py` during fixture setup.
3. Unhandled `httpx.ConnectError` or `httpcore.ConnectError` when running tests against backend URLs (`http://localhost:...`) that may be offline.

---

## Resolution Procedure

### 1. Update Async Fixture Decorators
Ensure every `async def` fixture is decorated with `@pytest_asyncio.fixture` rather than standard `@pytest.fixture`:

```python
import pytest_asyncio

@pytest_asyncio.fixture
async def rest_client(backend):
    ...
```

### 2. Harmonize Synchronous vs Asynchronous Fixtures
If a fixture consumes an `async def` fixture, it MUST also be declared as an `async def` fixture:

```python
# BAD (Synchronous generator consuming async fixture)
@pytest.fixture
def authenticated_client(backend, auth_token):
    ...

# GOOD (Asynchronous generator consuming async fixture)
@pytest_asyncio.fixture
async def authenticated_client(backend, auth_token):
    async with httpx.AsyncClient(...) as client:
        yield client
```

### 3. Configure `pytest.ini`
Create or update `pytest.ini` at the workspace root to ensure `pytest-asyncio` auto mode is active:

```ini
[pytest]
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

### 4. Implement Offline Backend Skip Guards
Wrap connection setup or requests in `conftest.py` with `try...except (httpx.ConnectError, httpx.ConnectTimeout)` to skip offline servers gracefully:

```python
@pytest_asyncio.fixture
async def rest_client(backend):
    if backend == BackendType.GRAPHQL:
        pytest.skip("Not a REST backend")
    url = BACKEND_URLS[backend]
    async with httpx.AsyncClient(base_url=url, timeout=5.0) as client:
        try:
            await client.get("/api/health")
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pytest.skip(f"Backend server for {backend.value} at {url} is offline")
        yield client
```
