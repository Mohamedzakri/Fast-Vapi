from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
from app.services.calendar_service import calendar_service
from app.services.email_service import email_service
import pytz

logger = logging.getLogger(__name__)


class ReminderService:
    """Service for scheduling and managing event reminders"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
        self.scheduled_reminders = {}  # Track scheduled reminders by event_id + interval
        self.default_intervals = [
            {"minutes": 10, "label": "10 minutes"},
            {"hours": 10, "label": "10 hours"},
            {"hours": 24, "label": "24 hours"}
        ]

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Reminder Scheduler started")

    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("🛑 Reminder Scheduler stopped")

    async def send_reminder(
            self,
            event_id: str,
            event_title: str,
            event_start: str,
            reminder_label: str,
            event_link: Optional[str] = None
    ):
        """
        Send a reminder email for an event

        Args:
            event_id: Event ID
            event_title: Title of the event
            event_start: Start time of the event
            reminder_label: Label for the reminder (e.g., "24 hours")
            event_link: Optional link to the event
        """
        logger.info(f"📧 Sending reminder for: {event_title} ({reminder_label} before)")

        success = await email_service.send_reminder_email(
            event_title=event_title,
            event_start=event_start,
            reminder_time=reminder_label,
            event_link=event_link
        )

        if success:
            logger.info(f"✅ Reminder sent successfully")
        else:
            logger.error(f"❌ Failed to send reminder")

        # Remove from scheduled reminders
        reminder_key = f"{event_id}_{reminder_label}"
        if reminder_key in self.scheduled_reminders:
            del self.scheduled_reminders[reminder_key]

    def schedule_reminder(
            self,
            event: Dict,
            reminder_interval: Dict
    ) -> bool:
        """
        Schedule a reminder for an event

        Args:
            event: Event dictionary from Google Calendar
            reminder_interval: Dict with 'minutes' or 'hours' key and 'label'

        Returns:
            bool: True if scheduled, False if not scheduled (past time or already scheduled)
        """
        try:
            # Extract event details
            event_id = event.get('id')
            event_title = event.get('summary', 'Untitled Event')
            event_link = event.get('htmlLink')

            # Parse event start time
            start = event.get('start', {})
            if 'dateTime' in start:
                event_start_str = start['dateTime']
                event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
            else:
                # All-day event
                event_start_str = start.get('date')
                event_start = datetime.fromisoformat(event_start_str).replace(
                    hour=0, minute=0, second=0, tzinfo=pytz.UTC
                )

            # Calculate reminder time
            if 'minutes' in reminder_interval:
                reminder_time = event_start - timedelta(minutes=reminder_interval['minutes'])
            elif 'hours' in reminder_interval:
                reminder_time = event_start - timedelta(hours=reminder_interval['hours'])
            else:
                logger.error(f"Invalid reminder interval: {reminder_interval}")
                return False

            reminder_label = reminder_interval['label']
            reminder_key = f"{event_id}_{reminder_label}"

            # Check if already scheduled
            if reminder_key in self.scheduled_reminders:
                logger.debug(f"⏭️ Reminder already scheduled: {event_title} ({reminder_label})")
                return False

            # Check if reminder time is in the past
            now = datetime.now(pytz.UTC)
            if reminder_time <= now:
                logger.debug(f"⏭️ Reminder time is in the past: {event_title} ({reminder_label})")
                return False

            # Schedule the reminder
            job = self.scheduler.add_job(
                self.send_reminder,
                trigger=DateTrigger(run_date=reminder_time),
                args=[
                    event_id,
                    event_title,
                    event_start.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    reminder_label,
                    event_link
                ],
                id=reminder_key,
                replace_existing=True
            )

            self.scheduled_reminders[reminder_key] = {
                'event_id': event_id,
                'event_title': event_title,
                'reminder_time': reminder_time,
                'reminder_label': reminder_label,
                'job_id': job.id
            }

            logger.info(f"⏰ Scheduled reminder: {event_title}")
            logger.info(f"   📅 Event time: {event_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"   🔔 Reminder time: {reminder_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"   ⏱️ Interval: {reminder_label} before")

            return True

        except Exception as e:
            logger.error(f"❌ Error scheduling reminder: {e}")
            return False

    async def schedule_reminders_for_upcoming_events(
            self,
            days_ahead: int = 7,
            custom_intervals: Optional[List[Dict]] = None
    ) -> Dict[str, int]:
        """
        Fetch upcoming events and schedule reminders

        Args:
            days_ahead: How many days ahead to fetch events
            custom_intervals: Custom reminder intervals (optional)

        Returns:
            Dict with stats about scheduled reminders
        """
        logger.info("=" * 80)
        logger.info(f"🔍 Checking for upcoming events (next {days_ahead} days)...")
        logger.info("=" * 80)

        try:
            # Fetch upcoming events
            events = calendar_service.get_upcoming_events(days_ahead=days_ahead)

            if not events:
                logger.info("📭 No upcoming events found")
                return {"events_found": 0, "reminders_scheduled": 0}

            logger.info(f"✅ Found {len(events)} upcoming event(s)")

            # Use custom intervals or default
            intervals = custom_intervals or self.default_intervals

            # Schedule reminders
            reminders_scheduled = 0
            for event in events:
                event_title = event.get('summary', 'Untitled Event')
                logger.info(f"\n📌 Processing: {event_title}")

                for interval in intervals:
                    if self.schedule_reminder(event, interval):
                        reminders_scheduled += 1

            logger.info("=" * 80)
            logger.info(f"✅ Scheduled {reminders_scheduled} reminder(s) for {len(events)} event(s)")
            logger.info("=" * 80)

            return {
                "events_found": len(events),
                "reminders_scheduled": reminders_scheduled
            }

        except Exception as e:
            logger.error(f"❌ Error scheduling reminders: {e}")
            return {"events_found": 0, "reminders_scheduled": 0, "error": str(e)}

    def get_scheduled_reminders(self) -> List[Dict]:
        """Get list of all scheduled reminders"""
        reminders = []
        for key, reminder in self.scheduled_reminders.items():
            reminders.append({
                "event_title": reminder['event_title'],
                "reminder_time": reminder['reminder_time'].isoformat(),
                "reminder_label": reminder['reminder_label'],
                "job_id": reminder['job_id']
            })
        return sorted(reminders, key=lambda x: x['reminder_time'])


# Singleton instance
reminder_service = ReminderService()
