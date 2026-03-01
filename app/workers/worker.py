import time
from datetime import datetime, timezone

from app.queue.redis_client import get_redis
from app.db.session import SessionLocal
from app.models.job import Job, JobStatus
from app.services.job_executor import execute_job

QUEUE_NAME = "main_queue"

def process_jobs():
    r = get_redis()
    print("Worker started. Waiting for jobs...")

    while True:
        # BRPOP blocks until a job is available
        # like timeout = 5s then loops
        result = r.brpop(QUEUE_NAME, timeout=5)
        if result is None:
            # no jobs in 5s, loop again
            continue

        _, job_id = result
        print(f"Picked up job: {job_id}")

        db = SessionLocal()
        job = None
        try:
            job = db.query(Job).filter(Job.id == job_id).first()

            if not job:
                print(f"Job {job_id} not found in DB. Skipping...")
                db.close()
                continue

            # Mark as processing
            job.status = JobStatus.processing
            job.last_attempt_at = datetime.now(timezone.utc)
            db.commit()

            # Execute the job (simulated HTTP call)
            execute_job(job_id)

            # Mark as completed
            job.status = JobStatus.completed
            db.commit()
            print(f"Job {job_id} completed.")

        except Exception as e:
            print(f"Job {job_id} failed: {e}")
            # Only update DB if we actually got the job row
            if job is not None:
                job.status = JobStatus.failed
                job.retry_count += 1
                db.commit()
        finally:
            db.close()
    
if __name__ == "__main__":
    process_jobs()