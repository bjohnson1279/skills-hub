---
name: conformance-test-suite-generator
description: Generates a pytest-based cross-backend conformance test suite for polyglot DDD projects.
---

# Conformance Test Suite Generator Skill

This skill documents the complete process for generating a pytest-based cross-backend conformance test suite for polyglot Domain-Driven Design (DDD) projects. It helps ensure parity across multiple backends (e.g., GraphQL TypeScript, Express REST, PHP REST) by asserting structural and behavioral equivalence.

## 1. Canonical Interface Analysis

To generate a conformance test suite, we first analyze the canonical frontend or client interface (e.g., a TypeScript `InventoryClient`).

1.  **Parse the Interface**: Extract all API operations from the client.
2.  **Extract Signatures**: Identify method signatures, parameter types, and return types.
3.  **Group Operations**: Categorize operations by domain capability (e.g., inventory CRUD, accounting, compliance).

*Note: For simplicity, regex-based parsing is often sufficient to extract method names and signatures from standard TypeScript interfaces.*

## 2. Infrastructure Generation

The generator must produce the following core infrastructure files:

### `conftest.py`
Contains pytest configuration, fixtures, and shared clients.
-   **Parametrized Backend Fixtures**: Allows tests to iterate over defined backends.
-   **Clients**: HTTP/GraphQL clients for sending requests.
-   **Auth**: JWT auth caching and management.
-   **Response Normalizers**: Functions to standardize responses from different backends.

### `comparator.py`
A deep comparison engine.
-   **DeepDiff**: Uses the `deepdiff` library for structural comparison.
-   **Unwrapping**: Strips GraphQL `{data: {...}}` envelopes.
-   **Normalization**: Converts between camelCase and snake_case.
-   **Volatile Stripping**: Removes volatile fields like database IDs, timestamps, and UUIDs to ensure deterministic comparisons.

### `canonical_types.yaml`
Golden reference JSON schemas.
-   Extracted from the TypeScript interfaces to serve as the source of truth for response shapes.

### `requirements.txt`
Dependencies required for the test suite:
```text
pytest
httpx
gql
deepdiff
pyyaml
jsonschema
pytest-json-report
```

## 3. Scenario Test Module Generation

Generate test modules based on domain capabilities.

1.  **Domain Grouping**: Group extracted operations (e.g., `test_inventory_crud.py`, `test_accounting.py`).
2.  **Parametrization**: Decorate each test with `@pytest.mark.parametrize('backend', [GRAPHQL, EXPRESS, PHP])`.
3.  **Execution**: Tests should send requests to all backends and collect responses.
4.  **Assertion**: Use `comparator.py` to assert structural and behavioral parity between the backends' responses and the canonical schema.

## 4. Normalization Strategies

Because REST and GraphQL backends format data differently, normalization is critical:

-   **GraphQL Envelope Unwrapping**: Extract the actual payload from the GraphQL `data` object.
-   **Case Conversion**: Normalize keys (camelCase ↔ snake_case).
-   **Volatile Field Stripping**: Ignore or zero out fields that change per request (IDs, timestamps).
-   **Tolerances**: Configure tolerances for timestamp drift and array ordering.

## 5. Verification & Reporting

-   **Report Generation**: Use `pytest-json-report` to generate machine-readable JSON reports.
-   **Summary Matrix**: Create a conformance summary matrix mapping scenarios to backend pass/fail rates.
-   **Integration**: Integrate the suite into CI/CD pipelines and master runner scripts.

## Concrete Example: Inventory App

Suppose the inventory app has three backends:
-   `GRAPHQL`: localhost:4000
-   `EXPRESS`: localhost:3000
-   `PHP`: localhost:8000

A generated test scenario in `test_inventory_crud.py` might look like:

```python
import pytest
from comparator import compare_responses

@pytest.mark.parametrize("backend_url", [
    "http://localhost:4000/graphql",
    "http://localhost:3000/api",
    "http://localhost:8000/api"
])
def test_get_inventory_item(backend_url, test_client):
    response = test_client.get(f"{backend_url}/items/1")
    # compare_responses normalizes and asserts against golden schema
    assert compare_responses(response.json(), "InventoryItem")
```
