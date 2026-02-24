# Distributed Job Processing System

## 1. High-Level Architecture

Client
  ↓
FastAPI Server (Job Producer)
  ↓
PostgreSQL (Job Metadata Storage)
  ↓
Redis (Queue Layer)
  ↓
Worker Pool (Async Workers)
  ↓
PostgreSQL (Status Updates)
  ↓
Prometheus Metrics Endpoint
  ↓
Grafana Dashboard


---

## 2. Core Components

### 2.1 API Server (FastAPI)

Responsibilities:
- Accept job creation requests
- Validate payload using Pydantic
- Enforce rate limiting
- Generate unique Job ID
- Store metadata in PostgreSQL
- Push job into Redis queue
- Expose job status endpoint
- Expose metrics endpoint

---

### 2.2 PostgreSQL (Persistent Storage)

Table: jobs

Fields:
- id (UUID, Primary Key)
- payload (JSONB)
- status (ENUM: queued, processing, completed, failed)
- retry_count (INTEGER)
- idempotency_key (VARCHAR, UNIQUE)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- last_attempt_at (TIMESTAMP)

Indexes:
- Index on status
- Index on created_at
- Unique index on idempotency_key

Purpose:
- Reliable job tracking
- Idempotency enforcement
- Recovery after crashes

---

### 2.3 Redis (Queue Layer)

Queues:
- main_queue
- retry_queue (delayed jobs)
- dead_letter_queue

Responsibilities:
- FIFO job processing
- Retry scheduling
- Temporary storage before worker execution

---

### 2.4 Worker Pool

Responsibilities:
- Continuously poll Redis
- Mark job as processing
- Execute job logic
- Handle failures
- Apply retry logic
- Move to DLQ if max retries exceeded
- Send heartbeat updates

Concurrency Model:
- Multiple async workers
- Horizontal scaling possible

---

### 2.5 Retry Strategy

Algorithm:
- retry_delay = base_delay * (2 ^ retry_count)
- Maximum retry threshold (5 attempts)
- After threshold → move to Dead Letter Queue

---

### 2.6 Idempotency Strategy

- Client sends idempotency_key
- Stored as UNIQUE in database
- Duplicate key → return existing job response
- Prevents duplicate execution

---

### 2.7 Observability

Metrics:
- jobs_processed_total
- jobs_failed_total
- jobs_retried_total
- queue_length
- active_workers
- processing_latency

Monitoring:
- Prometheus scrapes /metrics endpoint
- Grafana dashboards visualize performance

---

## 3. Failure Handling Strategy

Case 1: Worker crash mid-processing
- Use last_attempt_at
- If job stuck in processing beyond threshold → requeue

Case 2: Redis restart
- Jobs safely persisted in PostgreSQL
- Recovery script requeues incomplete jobs

Case 3: Duplicate submission
- Blocked via idempotency key constraint

Case 4: Max retry exceeded
- Move to Dead Letter Queue