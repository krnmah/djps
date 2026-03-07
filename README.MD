# Distributed Job Processing System (DJPS)

A production-grade background job processing system built with **FastAPI**, **PostgreSQL**, and **Redis**. Jobs are submitted via HTTP, persisted to a database, queued in Redis, and executed by a pool of workers — with retries, exponential backoff, a dead letter queue, rate limiting, Prometheus metrics, and Grafana dashboards.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Run with Docker Compose](#run-with-docker-compose)
  - [Local Development](#local-development)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Running Tests](#running-tests)
- [Observability](#observability)
- [Architecture Overview](#architecture-overview)

---

## Features

- **Job submission API** — `POST /jobs` accepts arbitrary JSON payloads
- **Idempotency** — optional `idempotency_key` prevents duplicate job creation
- **Rate limiting** — 10 requests/minute per IP on job submission (configurable)
- **Worker pool** — multiple `multiprocessing` workers process jobs concurrently
- **Retry logic** — up to 3 retries with exponential backoff (`2^n` seconds, capped at 60 s)
- **Dead Letter Queue** — jobs exceeding max retries are moved to the DLQ
- **Stuck-job recovery** — periodic scan requeues jobs stuck in `processing` longer than the threshold
- **Worker heartbeat** — each worker writes a TTL key to Redis so dead workers are detectable
- **Prometheus metrics** — counters for jobs created, completed, failed, and retried
- **Grafana dashboards** — pre-built dashboard visualises all job counters
- **Structured JSON logging** — every log line is JSON with `job_id` / `worker_id` correlation
- **Graceful shutdown** — in-progress jobs finish before the process exits
- **99% test coverage** — 179 unit + integration tests

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.133 + Uvicorn |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 (sync) |
| Queue | Redis 7 (BRPOP / RPUSH) |
| Migrations | Alembic |
| Settings | pydantic-settings v2 (reads `.env`) |
| Rate limiting | slowapi 0.1.9 |
| Metrics | prometheus-client 0.24 |
| Dashboards | Grafana |
| Logging | python-json-logger 4.0 |
| Workers | Python `multiprocessing` |
| Tests | pytest 9 + pytest-cov |
| Load tests | k6 |
| Containers | Docker Compose |

---

## Project Structure

```
djps/
├── app/
│   ├── api/
│   │   ├── deps.py               # get_db() FastAPI dependency
│   │   ├── router.py             # top-level router registration
│   │   └── routes/
│   │       ├── dlq.py            # GET  /dlq
│   │       ├── health.py         # GET  /health
│   │       ├── jobs.py           # POST /jobs, GET /jobs, GET /jobs/{id}
│   │       └── metrics.py        # GET  /metrics
│   ├── core/
│   │   ├── config.py             # Settings (pydantic-settings, .env)
│   │   ├── context.py            # ContextVars for job_id / worker_id
│   │   ├── limiter.py            # slowapi rate limiter
│   │   └── logging_config.py     # StructuredJsonFormatter + setup_logging()
│   ├── db/
│   │   ├── session.py            # SQLAlchemy engine + SessionLocal
│   │   └── migrations/           # Alembic versions
│   ├── metrics/
│   │   └── metrics.py            # JOBS_CREATED / COMPLETED / FAILED / RETRIED counters
│   ├── models/
│   │   └── job.py                # Job ORM model + JobStatus enum
│   ├── queue/
│   │   ├── producer.py           # enqueue_job(), push_to_dlq()
│   │   └── redis_client.py       # get_redis() singleton
│   ├── schemas/
│   │   └── job.py                # JobCreate, JobResponse, JobListResponse
│   ├── services/
│   │   ├── backoff.py            # calculate_backoff(retry_count)
│   │   ├── dlq_service.py        # get_dlq_jobs(db)
│   │   ├── job_executor.py       # execute_job() — simulated HTTP call
│   │   ├── job_service.py        # create_job(), get_job_by_id(), list_jobs()
│   │   └── retry_service.py      # handle_job_failure() — retry / DLQ routing
│   ├── workers/
│   │   ├── heartbeat.py          # update_heartbeat()
│   │   ├── manager.py            # WorkerManager (multiprocessing)
│   │   ├── recovery.py           # requeue_stuck_jobs()
│   │   └── worker.py             # process_jobs() main loop + graceful shutdown
│   └── main.py                   # create_app() factory
├── docker/
│   ├── docker-compose.yml        # dev stack (api, worker, pg, redis, prometheus, grafana)
│   ├── docker-compose-test.yml   # isolated test containers
│   ├── Dockerfile
│   ├── prometheus.yml
│   └── grafana/
├── docs/
│   ├── ARCHITECTURE.MD
│   └── DEVELOPMENT_PLAN.MD
├── scripts/
│   └── run_load_tests.ps1        # k6 smoke / load / spike runner
├── tests/
│   ├── unit/                     # pure unit tests (mocked dependencies)
│   ├── integration/              # real Postgres + Redis via test containers
│   ├── e2e/
│   └── load/                     # k6 scripts
├── alembic.ini
├── pytest.ini
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose)
- Python 3.11+ (for local development only)

### Run with Docker Compose

```bash
# Start everything: API, worker, Postgres, Redis, Prometheus, Grafana
docker compose -f docker/docker-compose.yml up --build

# API is available at http://localhost:8000
# Prometheus:         http://localhost:9090
# Grafana:            http://localhost:3000  (admin / admin)
```

### Run load tests (requires the dev stack to be running)

```powershell
# Smoke test (default)
.\scripts\run_load_tests.ps1

# Full load test
.\scripts\run_load_tests.ps1 -Test load

# Spike test
.\scripts\run_load_tests.ps1 -Test spike
```

### Local Development

```bash
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate          # Windows
source venv/bin/activate          # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment file and adjust if needed
cp .env.example .env

# 4. Start infrastructure only (Postgres + Redis)
docker compose -f docker/docker-compose.yml up postgres redis -d

# 5. Apply database migrations
alembic upgrade head

# 6. Start the API
uvicorn app.main:app --reload

# 7. Start a worker (separate terminal)
python -m app.workers.worker
```

---

## API Reference

### `POST /jobs` — Submit a job

**Rate limited:** 10 requests / minute per IP.

```json
// Request
{
  "payload": { "task": "send-email", "to": "user@example.com" },
  "idempotency_key": "order-42-email"   // optional
}

// Response 201
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "queued",
  "payload": { "task": "send-email", "to": "user@example.com" },
  "retry_count": 0,
  "idempotency_key": "order-42-email",
  "created_at": "2026-03-07T10:00:00",
  "updated_at": "2026-03-07T10:00:00",
  "last_attempt_at": null
}
```

| Status | Meaning |
|---|---|
| `201` | Job created and queued |
| `200` | Idempotent — existing job returned |
| `409` | Idempotency key race condition (retry the request) |
| `422` | Validation error |
| `429` | Rate limit exceeded |

---

### `GET /jobs/{job_id}` — Get job status

```
GET /jobs/3fa85f64-5717-4562-b3fc-2c963f66afa6
```

Returns the `JobResponse` object above, or `404` if not found.

---

### `GET /jobs` — List jobs

```
GET /jobs?status=failed&limit=20&offset=0
```

| Query param | Type | Default | Description |
|---|---|---|---|
| `status` | `queued\|processing\|completed\|failed` | — | Filter by status |
| `limit` | `1–100` | `20` | Page size |
| `offset` | `≥ 0` | `0` | Records to skip |

```json
// Response 200
{
  "items": [ /* JobResponse objects */ ],
  "total": 142,
  "limit": 20,
  "offset": 0
}
```

---

### `GET /dlq` — Dead Letter Queue contents

Returns an array of `JobResponse` objects for all jobs currently in the DLQ.

---

### `GET /health` — Health check

```json
{ "status": "ok" }
```

---

### `GET /metrics` — Prometheus metrics

Raw Prometheus text format. Scraped automatically by Prometheus.

---

## Configuration

All settings are read from environment variables (or from a `.env` file). Copy `.env.example` to `.env` and adjust.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://djps:djps@localhost:5432/djps` | SQLAlchemy database URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `SIMULATED_JOB_URL` | `https://httpbin.org/delay/1` | URL the worker calls to simulate work |
| `SIMULATED_FAILURE_RATE` | `0.2` | Fraction of jobs to fail deliberately (0–1) |
| `SIMULATED_TIMEOUT` | `5.0` | Timeout (s) for the simulated HTTP call |
| `MAX_JOB_RETRIES` | `3` | Max retry attempts before moving to DLQ |
| `BACKOFF_BASE` | `2.0` | Exponential backoff base (seconds) |
| `MAX_BACKOFF` | `60.0` | Backoff ceiling (seconds) |
| `WORKER_HEARTBEAT_TTL` | `30` | Redis key TTL for worker heartbeats (s) |
| `STUCK_JOB_THRESHOLD` | `60` | Seconds before a `processing` job is considered stuck |
| `STUCK_CHECK_INTERVAL` | `10` | Worker loop cycles between stuck-job scans |
| `NUM_WORKERS` | `2` | Number of worker processes spawned by WorkerManager |

---

## Running Tests

```bash
# Start test infrastructure (Postgres on 5433, Redis on 6380)
docker compose -f docker/docker-compose-test.yml up -d

# Run all tests
pytest tests/

# Run with coverage report
pytest tests/ --cov=app --cov-report=term-missing

# Run only unit tests (no containers needed)
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

Current coverage: **99%** across 470 statements (179 tests).

---

## Observability

### Prometheus metrics

| Metric | Type | Description |
|---|---|---|
| `jobs_created_total` | Counter | Jobs successfully created via POST /jobs |
| `jobs_completed_total` | Counter | Jobs completed by a worker |
| `jobs_failed_total` | Counter | Jobs permanently failed (sent to DLQ) |
| `jobs_retried_total` | Counter | Individual retry attempts |

### Grafana

Open `http://localhost:3000` (admin / admin) after starting the dev stack. The pre-configured **DJPS Dashboard** shows all four counters as time-series graphs.

### Structured logs

Every log line is JSON. Fields always present: `timestamp`, `level`, `logger`, `message`. Job-processing logs also include `job_id` and `worker_id` via `contextvars`.

```json
{
  "timestamp": "2026-03-07T10:15:32",
  "level": "INFO",
  "logger": "app.workers.worker",
  "message": "Job completed.",
  "job_id": "3fa85f64-...",
  "worker_id": "a1b2c3d4-..."
}
```

---

## Architecture Overview

See [docs/ARCHITECTURE.MD](docs/ARCHITECTURE.MD) for the full design document, including component interactions, failure handling strategy, and scaling trade-offs.
