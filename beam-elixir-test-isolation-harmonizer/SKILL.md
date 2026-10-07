---
name: beam-elixir-test-isolation-harmonizer
description: >
  Audits, diagnoses, and harmonizes BEAM and Elixir ExUnit test suites to eliminate cross-test process leaks, uncleaned Registry entries, DynamicSupervisor child collisions, and ETS table pollution.
---

# BEAM / Elixir Test Isolation Harmonizer

This skill standardizes process isolation, clean teardowns, and registry pruning across Elixir/Phoenix ExUnit test suites.

---

## Capabilities

1. **Registry Cleanup (`on_exit` Hooks)**:
   - Diagnoses cascading test failures where global or partitioned registries (`Registry.register/3`) hit conversation or process limits (e.g. `{:error, :too_many_conversations}`).
   - Automatically injects `on_exit/1` cleanup handlers that call `Registry.unregister/2` or kill ephemeral test processes before subsequent tests execute.

2. **DynamicSupervisor Child Teardown**:
   - Ensures mock or dynamically spawned test workers are terminated gracefully with `DynamicSupervisor.terminate_child/2`, preventing orphan workers from consuming node resources or responding to downstream calls.

3. **ETS Table Isolation**:
   - Diagnoses named ETS table collision errors (`{:error, :already_exists}`) when running tests in parallel (`async: true`).
   - Harmonizes test fixtures to use unique table identifiers via `System.unique_integer([:positive])` or restricts concurrency to `async: false` for shared resources.

4. **Dockerized Phoenix Execution**:
   - Works seamlessly with Docker Compose test harnesses (`docker compose run --rm app mix test`) and standard local `mix test` runners.

---

## Best Practice Patterns

### 1. Robust Registry Cleanup in ExUnit
```elixir
setup do
  unique_id = "test_conv_#{System.unique_integer([:positive])}"
  {:ok, _pid} = Registry.register(MyApp.ConversationRegistry, unique_id, %{started_at: DateTime.utc_now()})

  # Register on_exit hook to guarantee unregistration even if assertions fail
  on_exit(fn ->
    Registry.unregister(MyApp.ConversationRegistry, unique_id)
  end)

  {:ok, conversation_id: unique_id}
end
```

### 2. DynamicSupervisor Child Isolation
```elixir
setup do
  {:ok, pid} = DynamicSupervisor.start_child(MyApp.TestSupervisor, {MyApp.Worker, []})

  on_exit(fn ->
    if Process.alive?(pid) do
      DynamicSupervisor.terminate_child(MyApp.TestSupervisor, pid)
    end
  end)

  {:ok, worker_pid: pid}
end
```

### 3. Diagnosing Leaks in ExUnit
When a test fails with process count limits:
```bash
# Run specific test with trace output and sync execution:
docker compose run --rm app mix test test/my_app/conversation_test.exs --trace --max-failures 1
```
