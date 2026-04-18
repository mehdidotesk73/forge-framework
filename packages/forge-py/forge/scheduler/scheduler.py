"""APScheduler wrapper for Forge's internal pipeline scheduler."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from forge.config import PipelineConfig, ProjectConfig
from forge.pipeline.runner import PipelineRunner
from forge.storage.engine import StorageEngine

log = logging.getLogger(__name__)


class ForgeScheduler:
    def __init__(
        self,
        config: ProjectConfig,
        runner: PipelineRunner,
        engine: StorageEngine,
    ) -> None:
        self.config = config
        self.runner = runner
        self.engine = engine
        self._scheduler = BackgroundScheduler()
        self._running = False

    def start(self) -> None:
        for p in self.config.pipelines:
            if p.schedule:
                self._register_pipeline(p)
        self._scheduler.start()
        self._running = True
        log.info("Forge scheduler started")

    def stop(self) -> None:
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False

    def _register_pipeline(self, p: PipelineConfig) -> None:
        try:
            parts = p.schedule.split()
            if len(parts) == 5:
                minute, hour, dom, month, dow = parts
            else:
                log.warning("Invalid cron expression for %s: %s", p.name, p.schedule)
                return

            trigger = CronTrigger(
                minute=minute, hour=hour,
                day=dom, month=month, day_of_week=dow,
            )
            self._scheduler.add_job(
                self._run_pipeline,
                trigger=trigger,
                args=[p],
                id=f"pipeline_{p.name}",
                replace_existing=True,
                misfire_grace_time=60,
            )
            log.info("Scheduled pipeline '%s' with cron: %s", p.name, p.schedule)
        except Exception as exc:
            log.error("Failed to schedule pipeline '%s': %s", p.name, exc)

    def _run_pipeline(self, p: PipelineConfig) -> None:
        log.info("Scheduler firing pipeline: %s", p.name)
        try:
            defn = self.runner.load_pipeline(p.module, p.function)
            result = self.runner.run(defn)
            log.info("Pipeline '%s' completed: %s", p.name, result)
        except Exception as exc:
            log.error("Pipeline '%s' failed: %s", p.name, exc)

    def trigger_now(self, pipeline_name: str) -> None:
        """Manually fire a scheduled pipeline immediately."""
        for p in self.config.pipelines:
            if p.name == pipeline_name and p.schedule:
                job = self._scheduler.get_job(f"pipeline_{pipeline_name}")
                if job:
                    job.modify(next_run_time=__import__("datetime").datetime.now())
                    return
        raise ValueError(f"No scheduled pipeline named '{pipeline_name}'")
