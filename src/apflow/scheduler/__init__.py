"""
APFlow Scheduler Module

This module provides task scheduling capabilities for apflow, including:
- Internal scheduler: Built-in scheduler using APScheduler for standalone deployment
- External gateway: Integration with external schedulers (Webhook, iCal export)

Usage:
    # Internal scheduler
    from apflow.scheduler import InternalScheduler
    scheduler = InternalScheduler()
    await scheduler.start()

    # iCal export
    from apflow.scheduler.gateway import ICalExporter
    exporter = ICalExporter()
    ical_content = await exporter.export_tasks(user_id="user123")
"""

from apflow.scheduler.base import BaseScheduler, SchedulerState
from apflow.scheduler.internal import InternalScheduler

__all__ = [
    "BaseScheduler",
    "SchedulerState",
    "InternalScheduler",
]
