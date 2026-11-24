"""
Background Autonomous Scheduler for RouteRanker.
Periodically runs the online data collector + self-training pipeline.
"""
import os
import sys
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from analytics.auto_retrain import run_autonomous_cycle


def scheduled_job():
    print("[scheduler] Running autonomous data check and self-training evaluation...")
    result = run_autonomous_cycle(force_retrain=False)
    print(f"[scheduler] Cycle finished: {result.get('status')}")


if __name__ == "__main__":
    interval_hours = int(os.getenv("ROUTERANKER_RETRAIN_INTERVAL_HOURS", "24"))
    scheduler = BlockingScheduler()
    scheduler.add_job(scheduled_job, "interval", hours=interval_hours, id="autonomous_retrain_job")
    print(f"[scheduler] Autonomous ML self-training scheduler active (every {interval_hours}h)...")
    scheduler.start()
