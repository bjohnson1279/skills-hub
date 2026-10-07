---
name: php-container-mock-test-harness
description: Standardizes mocking static ServiceContainer singletons, handling dependency overrides, suppressing error_log outputs with output buffering, and cleanup across PHPUnit unit tests.
---

# PHP Container Mock Test Harness

This skill provides step-by-step guidelines for safely mocking dependency injection containers (`ServiceContainer`) and testing error paths in PHPUnit without polluting test runner logs.

## When to Use

1. Testing domain services or handlers that invoke static `ServiceContainer` accessors (e.g. `ServiceContainer::reorderPolicyService()`).
2. Testing error handlers and catch blocks that output via `error_log()`.
3. Isolating unit tests from real container bindings or external services.

---

## Pattern Implementation

### 1. Register Mock Service Instance in Container

Use Illuminate container's `instance()` method on `ServiceContainer::getInstance()`:

```php
use InventoryApp\Infrastructure\ServiceContainer;
use InventoryApp\Domain\Procurement\Services\ReorderPolicyService;

$mockPolicyService = $this->createMock(ReorderPolicyService::class);
$mockPolicyService->method('checkPolicy')
    ->willThrowException(new \Exception('Policy evaluation failed'));

$container = ServiceContainer::getInstance();
$container->instance(ReorderPolicyService::class, $mockPolicyService);
```

### 2. Suppress Log Side Effects via Output Buffering

When testing code paths that output messages via `error_log()`, wrap the execution block in output buffering to maintain clean test output:

```php
ob_start();
try {
    $result = $this->service->executeTask($arg1, $arg2);
} finally {
    ob_end_clean();
}
```

### 3. Clean Up Mock Container Instances

To prevent state leakage between unit tests, clear container instances after assertions:

```php
$container->forgetInstance(ReorderPolicyService::class);
```

### Complete Test Method Example

```php
public function testGenerateDemandForecastErrorPath(): void
{
    $sku = new SKU('TEST-SKU');
    $locationId = new LocationId('LOC-1');

    $mockPolicyService = $this->createMock(ReorderPolicyService::class);
    $mockPolicyService->method('checkPolicy')
        ->willThrowException(new \Exception('Policy evaluation failed'));

    $container = ServiceContainer::getInstance();
    $container->instance(ReorderPolicyService::class, $mockPolicyService);

    ob_start();
    $forecast = $this->forecaster->generateDemandForecast($sku, $locationId, 30, 1.0, $product);
    ob_end_clean();

    $this->assertNotNull($forecast);
    $this->assertEquals($sku, $forecast->sku);

    $container->forgetInstance(ReorderPolicyService::class);
}
```

---

## Refactoring Mockery to Native PHPUnit Mocks

When tests use `Mockery` in codebases where `mockery/mockery` is not installed in `composer.json`, tests will fail with `Class 'Mockery' not found`. Convert them directly to PHPUnit mock syntax:

| Mockery Syntax | PHPUnit Equivalent |
| :--- | :--- |
| `Mockery::mock(Service::class)` | `$this->createMock(Service::class)` |
| `Mockery::close()` | *(Remove completely; PHPUnit cleans up assertions automatically)* |
| `$mock->shouldReceive('fn')->once()->andReturn($val)` | `$mock->expects($this->once())->method('fn')->willReturn($val)` |
| `$mock->shouldReceive('fn')->with($a, $b)->andReturn($val)` | `$mock->expects($this->once())->method('fn')->with($a, $b)->willReturn($val)` |
| `$mock->shouldReceive('fn')->andThrow(new Exception(...))` | `$mock->expects($this->once())->method('fn')->willThrowException(new Exception(...))` |

