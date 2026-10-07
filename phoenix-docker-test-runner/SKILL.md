---
name: phoenix-docker-test-runner
description: Standardizes running, diagnosing, and repairing Phoenix/Elixir test suites and precommit checks in containerized Docker/Docker-Compose environments, including MIX_ENV isolation, volume caching, and test support compilation.
---

# Phoenix Docker Test Runner & Environment Harmonizer

This skill standardizes executing tests, precommit hooks, and environment diagnostics for Phoenix/Elixir applications running inside Docker/Docker-Compose on Windows, macOS, and Linux.

---

## Capabilities & Problem Diagnosis

When developing or pair-programming on Phoenix applications where Elixir is containerized (or not installed directly on the host machine), tests and precommit checks must be executed through `docker compose run` or `docker compose exec`.

### 1. The `MIX_ENV` Container Poisoning Bug
* **Symptom**: Running `docker compose run --rm app mix test` fails with:
  ```
  error: module MyAppWeb.ConnCase is not loaded and could not be found
  ** (CompileError) test/.../error_html_test.exs: cannot compile module
  ```
* **Root Cause**: `docker-compose.yml` hardcodes `environment: - MIX_ENV=dev`. In Phoenix apps, `mix.exs` sets:
  ```elixir
  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]
  ```
  When `MIX_ENV=dev` is injected by Docker into the container environment, `mix test` and `mix precommit` inherit `:dev` rather than defaulting to `:test`. Consequently, `test/support` (containing `ConnCase` and test helpers) is completely excluded from compilation.
* **Resolution**: Remove hardcoded `MIX_ENV=dev` from `docker-compose.yml`. Mix will naturally default to `:dev` when starting the server (`mix phx.server`), and correctly select `:test` when running `mix test` and `mix precommit`.

### 2. The `mix.lock` Container Volume Dependency Mismatch
* **Symptom**: Running `docker compose run --rm app mix test` or `mix precommit` fails with:
  ```
  Unchecked dependencies for environment test:
  * <package_name> (Hex package)
    lock mismatch: the dependency is out of date. To fetch locked version run "mix deps.get"
  ** (Mix) Can't continue due to errors on dependencies
  ```
* **Root Cause**: When dependencies in `mix.lock` are updated (e.g. security bumps, PR merges), the persistent Docker volume named `deps` still caches the older version of the downloaded package.
* **Resolution**: Execute `docker compose run --rm app mix deps.get` to synchronize Hex packages in the container volume before compiling or executing tests.

---

## Standard Workflows

### 1. Verifying Container & Dockerfile Setup
Ensure `docker-compose.yml` uses named volumes for `deps:` and `build:` so Linux BEAM build artifacts stay inside the container and don't conflict with host filesystems:

```yaml
services:
  app:
    build: .
    ports:
      - "4000:4000"
    volumes:
      - .:/app
      - deps:/app/deps
      - build:/app/_build
    environment:
      - PHX_HOST=localhost
    stdin_open: true
    tty: true

volumes:
  deps:
  build:
```

### 2. Running Test Suites via Docker Compose

#### Full Test Suite
```bash
docker compose run --rm app mix test
```

#### Running a Specific Test File
```bash
docker compose run --rm app mix test test/my_app_web/live/dashboard_live_test.exs
```

#### Running a Specific Line Number / Single Test
```bash
docker compose run --rm app mix test test/my_app_web/live/dashboard_live_test.exs:14
```

### 3. Running Precommit Verification
To run the full suite with compiler warning guards, unused dependency pruning, code formatting, and test execution:
```bash
docker compose run --rm app mix precommit
```

### 4. Dependency Synchronization (`mix.lock` updates)
Whenever `mix.lock` is modified or a lock mismatch is detected:
```bash
docker compose run --rm app mix deps.get
```

### 5. Interactive Debugging & Shell Access
If you need an interactive IEx session or bash shell inside the test container:
```bash
docker compose run --rm app iex -S mix
# Or bash:
docker compose run --rm app bash
```

---

## Common Pitfalls & Guardrails

1. **Forcing `MIX_ENV=dev` at Service Level**: Never hardcode `MIX_ENV=dev` in `docker-compose.yml`. Let Mix's `preferred_envs` in `mix.exs` govern task environments.
2. **Mounting `_build` Directly to Windows Filesystem**: Always use Docker named volumes (`- build:/app/_build` and `- deps:/app/deps`). Mounting `_build` directly into Windows NTFS causes severe BEAM file-locking latency and cross-platform compilation failures.
3. **Secret Key Base in Test Config**: Ensure `config/test.exs` uses a fallback dummy secret key:
   ```elixir
   secret_key_base: System.get_env("SECRET_KEY_BASE") || "a_very_long_dummy_secret_key_base_for_testing_purposes_only_12345678"
   ```
4. **Testing Concurrency**: In LiveView test cases, always use `ConvoSimWeb.ConnCase, async: true` unless modifying global shared GenServer registries that require synchronous synchronization.
5. **Outdated Container Volume Dependencies**: After git pulls, branch switches, or PR merges touching `mix.lock`, always execute `docker compose run --rm app mix deps.get` before running `mix test` or `mix precommit`.
