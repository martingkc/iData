import subprocess
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore  # <--- NEW IMPORT
from apscheduler.jobstores.base import JobLookupError

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rclone-api")

app = FastAPI()

# ---------------------------------------------------------
# PERSISTENCE CONFIGURATION
# ---------------------------------------------------------
# We define a job store that uses a local SQLite file named 'jobs.sqlite'
# This file will be created automatically in your project folder.
jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///jobs.sqlite")}

# We pass this jobstore into the scheduler
# 'misfire_grace_time': If the server was down and a job was missed,
# how many seconds late can it be and still be allowed to run? (3600 = 1 hour)
job_defaults = {"misfire_grace_time": 3600}

scheduler = BackgroundScheduler(jobstores=jobstores, job_defaults=job_defaults)
# ---------------------------------------------------------


@app.on_event("startup")
def start_scheduler():
    # Only start if not already running
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started with SQLite persistence.")


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()


# --- The rest of your logic remains the same ---


def run_rclone_sync(source: str, dest: str, job_id: str):
    logger.info(f"Starting job {job_id}: Syncing {source} to {dest}")
    try:
        # Check if rclone is installed first
        result = subprocess.run(
            ["rclone", "sync", source, dest, "--log-level", "INFO"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"Job {job_id} Success.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Job {job_id} Failed: {e.stderr}")
    except FileNotFoundError:
        logger.error("Rclone not found! Make sure rclone is in your system PATH.")


class SyncJob(BaseModel):
    job_id: str
    source: str
    destination: str
    interval_minutes: int


@app.post("/jobs/schedule")
def schedule_sync(job: SyncJob):
    # Check if job exists in the DATABASE now
    if scheduler.get_job(job.job_id):
        raise HTTPException(status_code=400, detail="Job ID already exists")

    scheduler.add_job(
        run_rclone_sync,
        trigger=IntervalTrigger(minutes=job.interval_minutes),
        id=job.job_id,
        args=[job.source, job.destination, job.job_id],
        replace_existing=True,
        name=f"Sync {job.source} -> {job.destination}",
    )
    return {"status": "scheduled", "job_id": job.job_id, "persistence": "saved to disk"}


@app.get("/jobs")
def list_jobs():
    """
    This will now return jobs even after you restart the server.
    """
    jobs = []
    # Scheduler reads from SQLite automatically here
    for job in scheduler.get_jobs():
        jobs.append(
            {"id": job.id, "next_run": str(job.next_run_time), "args": job.args}
        )
    return {"active_jobs": jobs}


@app.delete("/jobs/{job_id}")
def remove_job(job_id: str):
    try:
        scheduler.remove_job(job_id)
        return {"status": "removed", "job_id": job_id}
    except JobLookupError:
        raise HTTPException(status_code=404, detail="Job not found")
