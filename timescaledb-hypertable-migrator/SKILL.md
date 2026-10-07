---
name: timescaledb-hypertable-migrator
description: Standardizes TimescaleDB time-series hypertable configuration (ledger_entries, dispatch_records) and automated database backup/restore scripts across PostgreSQL containerized environments. Activate this skill when working on TimescaleDB extension setup, time-series tables, or automated database backup automation scripts.
---

# TimescaleDB Hypertable Migrator

This skill standardizes time-series hypertable partitioning with TimescaleDB on PostgreSQL, along with automated snapshot backup and restore helpers across development and containerized environments.

## When to Activate

Activate this skill when:
- Creating time-series ledger or dispatch audit tables partitioned by timestamp (`occurred_at`, `dispatched_at`).
- Configuring `docker-compose.yml` with TimescaleDB images (`timescale/timescaledb:latest-pg15` / `pg16`).
- Writing or maintaining automated database snapshot backup and restore scripts (`infra/db/backup.sh`, `backup.ps1`, `restore.sh`).

---

## Best Practices & Guidelines

### 1. TimescaleDB Extension & Hypertable Setup
* Enable extension: `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;`
* Convert table to hypertable:
  ```sql
  SELECT create_hypertable('ledger_entries', 'occurred_at', if_not_exists => TRUE);
  SELECT create_hypertable('dispatch_records', 'dispatched_at', if_not_exists => TRUE);
  ```

### 2. Automated DB Snapshot Backup Scripts
* Schedule compressed snapshot outputs (`.sql.gz`) with timestamps (`YYYYMMDD_HHMMSS`).
* Provide cross-platform script wrappers:
  - Linux/macOS: `infra/db/backup.sh` using `pg_dump -Z 9`
  - Windows: `infra/db/backup.ps1` using `gzip` compression stream
* Provide restore utility (`restore.sh`) taking a Target `.sql.gz` file argument.
