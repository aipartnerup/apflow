"""
External Scheduler Gateway

This module provides integration with external schedulers through:
- Webhook: HTTP endpoints for external schedulers to trigger tasks
- iCal: Export scheduled tasks in iCalendar format for calendar applications

Supported external schedulers:
- cron (via webhook)
- Kubernetes CronJob (via webhook)
- APScheduler (via webhook or direct integration)
- Google Calendar (via iCal export)
- Any calendar app supporting iCal (Outlook, Apple Calendar, etc.)
"""

from apflow.scheduler.gateway.webhook import WebhookGateway, WebhookConfig
from apflow.scheduler.gateway.ical import ICalExporter

__all__ = [
    "WebhookGateway",
    "WebhookConfig",
    "ICalExporter",
]
