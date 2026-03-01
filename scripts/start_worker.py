import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.workers.worker import process_jobs

if __name__ == "__main__":
    process_jobs()