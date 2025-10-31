# app/services/reminder_service.py
from __future__ import annotations
import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.message import EmailMessage
import smtplib, ssl
from typing import Dict, Set, Any, List

# Reuse your existing Google Calendar client
# (You already import calendar_service elsewhere, e.g. in your test file.)
from app.services.calendar_service import calendar_service

logger = logging.getLogger(__name__)

ROME_TZ = ZoneInfo("Europe/Rome")

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _dt_to_local(dt: datetime) -> datetime:
    # dt expected to be timezone-aware
    return dt.astimezone(ROME_TZ)

class EmailNotifier:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender = os.getenv("SENDER_EMAIL")
        self.password = os.getenv("SENDER_PASSWORD")  # Gmail App Password
        self.receiver = os.getenv("RECEIVER_EMAIL", self.sender)

        missing = [k for k,v in {
            "SENDER_EMAIL": self.sender,
            "SENDER_PASSWORD": self.password
        }.items() if not v]
        if missing:
            raise RuntimeError(f"Missing required email env vars: {', '.join(missing)}")

    def send(self, subject: str, body: str):
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = self.receiver
        msg["Subject"] = subject
        msg.set_content(body)

        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls(context=context)
            server.login(self.sender, self.password)
            server.send_message(msg)

class ReminderService:
    """
    Polls Calendar for events in the next 5 minutes and emails a reminder.
    Uses an in-memory cache so the same event is not emailed repeatedly.
    """
    def __init__(self, notifier: EmailNotifier):
        self.notifier = notifier
        # Remember event IDs we've notified for a short window
        self._notified_event_ids: Set[str] = set()
        # soft TTL in minutes — clear cache occasionally
        self._last_cache_reset = _now_utc()

    def _maybe_clear_cache(self):
        if (_now_utc() - self._last_cache_reset) > timedelta(minutes=30):
            self._notified_event_ids.clear()
            self._last_cache_reset = _now_utc()

    def _extract_dt(self, event: Dict[str, Any]) -> datetime | None:
        """
        Normalizes Google Calendar event start time to aware UTC datetime.
        Handles all-day events (date) and normal events (dateTime).
        """
        start = event.get("start", {})
        if "dateTime" in start:
            # Example: 2025-10-31T10:55:00+01:00
            return datetime.fromisoformat(start["dateTime"]).astimezone(timezone.utc)
        if "date" in start:
            # All-day event — treat as midnight local
            local_midnight = datetime.fromisoformat(start["date"]).replace(hour=0, minute=0, second=0, microsecond=0)
            local_midnight = local_midnight.replace(tzinfo=ROME_TZ)
            return local_midnight.astimezone(timezone.utc)
        return None

    def _format_subject_body(self, event: Dict[str, Any]) -> tuple[str, str]:
        title = event.get("summary", "(No title)")
        start_dt_utc = self._extract_dt(event)
        start_local = _dt_to_local(start_dt_utc) if start_dt_utc else None
        location = event.get("location")
        hangout_link = event.get("hangoutLink")
        html_link = event.get("htmlLink")  # Calendar web link

        subject = f"Reminder: {title} in ~5 minutes"
        lines = [f"Event: {title}"]
        if start_local:
            lines.append(f"Starts: {start_local.strftime('%Y-%m-%d %H:%M')} ({start_local.tzinfo.key})")
        if location:
            lines.append(f"Location: {location}")
        if hangout_link:
            lines.append(f"Meet/Call: {hangout_link}")
        if html_link:
            lines.append(f"Open in Calendar: {html_link}")
        return subject, "\n".join(lines)

    def _in_next_five_minutes(self, event: Dict[str, Any]) -> bool:
        start_dt_utc = self._extract_dt(event)
        if not start_dt_utc:
            return False
        now = _now_utc()
        return now <= start_dt_utc <= (now + timedelta(minutes=5))

    async def check_and_notify_once(self) -> List[str]:
        """
        Runs one scan. Returns a list of event IDs we sent email for (for logging/tests).
        Expects your calendar_service to have a method to fetch events between timeMin and timeMax.
        If not, you can add a helper there; otherwise we call a generic 'list events' with a time window.
        """
        self._maybe_clear_cache()

        now = _now_utc()
        window_end = now + timedelta(minutes=5)

        # Your calendar_service already works in your test script (get_recent_events).
        # We'll ask for events in [now, now+5m]. Adjust the method name if your service differs.
        # The common Google Calendar filter uses RFC3339 strings and 'timeMin'/'timeMax'.
        try:
            events = calendar_service.get_events(
                time_min=now.isoformat(),
                time_max=window_end.isoformat(),
                max_results=10,
                single_events=True,
                order_by="startTime"
            )
        except AttributeError:
            # Fallback if your service doesn’t expose get_events; try a more generic method if you have one.
            events = calendar_service.list_events(
                time_min=now.isoformat(),
                time_max=window_end.isoformat(),
                max_results=10,
                single_events=True,
                order_by="startTime"
            )

        if not events:
            return []

        sent_ids: List[str] = []
        for ev in events:
            ev_id = ev.get("id")
            if not ev_id:
                continue
            if ev_id in self._notified_event_ids:
                continue
            if not self._in_next_five_minutes(ev):
                continue

            subject, body = self._format_subject_body(ev)
            try:
                self.notifier.send(subject, body)
                self._notified_event_ids.add(ev_id)
                sent_ids.append(ev_id)
                logger.info("Sent reminder for event %s", ev_id)
            except Exception as e:
                logger.exception("Failed to send reminder for %s: %s", ev_id, e)

        return sent_ids


class ReminderLoop:
    """
    Minimal polling loop you can start/stop during FastAPI lifespan.
    """
    def __init__(self, service: ReminderService, interval_seconds: int = 60):
        self.service = service
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    async def _run(self):
        logger.info("Reminder loop started (every %ss)", self.interval)
        try:
            while self._running:
                await self.service.check_and_notify_once()
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            logger.info("Reminder loop cancelled.")
        finally:
            logger.info("Reminder loop stopped.")

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self._running and self._task:
            self._running = False
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
