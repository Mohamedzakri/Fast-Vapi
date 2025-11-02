import asyncio
from datetime import datetime
import logging
from app.services.calendar_service import calendar_service
from app.services.database_service import DatabaseService
from app.services.reminder_service import reminder_service

logger = logging.getLogger(__name__)


class BackgroundMonitor:
    """Background task for monitoring Google Calendar events and auto-scheduling reminders"""

    def __init__(self):
        self.running = False
        self.task = None
        self.check_interval = 3
        self.db_service = None

        # Reminder intervals - customize these as needed!
        self.reminder_intervals = [
            {"minutes": 1, "label": "1 minutes"}
        ]

    async def monitor_calendar(self, db):
        """
        Background task that continuously monitors calendar for new events
        and automatically schedules reminders

        Args:
            db: Database instance
        """
        self.running = True
        self.db_service = DatabaseService(db)

        logger.info("=" * 80)
        logger.info("AUTOMATED REMINDER SYSTEM STARTED")
        logger.info(f"Checking for new events every {self.check_interval} seconds")
        logger.info(f"Auto-scheduling reminders: {', '.join([i['label'] for i in self.reminder_intervals])}")
        logger.info("=" * 80)

        # Initial check on startup
        await self.check_and_schedule_reminders()

        while self.running:
            try:
                await asyncio.sleep(self.check_interval)
                await self.check_and_schedule_reminders()

            except Exception as e:
                logger.error(f"Background monitoring error: {e}")
                await asyncio.sleep(self.check_interval)

    async def check_and_schedule_reminders(self):
        """Check for new/upcoming events and schedule reminders"""
        try:
            """
            logger.info("\n" + "=" * 80)
            logger.info(f"🔍 Checking for events... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            logger.info("=" * 80)
            """
            # Check for new events (created/modified recently)
            new_events = calendar_service.detect_new_events()

            if new_events:
                logger.info(f"Found {len(new_events)} new/modified event(s)")

                for event in new_events:
                    formatted = calendar_service.format_event_log(event)

                    logger.info(f"\n New Event Detected:")
                    logger.info(f"   Title: {formatted['title']}")
                    logger.info(f"   Start: {formatted['start_time']}")
                    logger.info(f"   End: {formatted['end_time']}")

                    # Save to MongoDB
                    try:
                        await self.db_service.db.calendar_events.insert_one({
                            **formatted,
                            'detected_at': datetime.utcnow(),
                            'source': 'background_monitoring'
                        })
                        logger.info("   Saved to MongoDB")
                    except Exception as db_error:
                        logger.error(f"   MongoDB save failed: {db_error}")

                    # Auto-schedule reminders for this event
                    logger.info(f"   Scheduling reminders...")
                    for interval in self.reminder_intervals:
                        if reminder_service.schedule_reminder(event, interval):
                            logger.info(f"      Scheduled: {interval['label']} before")
                        else:
                            logger.debug(f"     Skipped: {interval['label']} before")

                    # Log to file
                    calendar_service.log_event_to_file(formatted)

            # Also check upcoming events (next 7 days) to catch any we might have missed

            stats = await reminder_service.schedule_reminders_for_upcoming_events(
                days_ahead=7,
                custom_intervals=self.reminder_intervals
            )

            if stats.get('reminders_scheduled', 0) > 0:
                logger.info(f"   Scheduled {stats['reminders_scheduled']} additional reminder(s)")
            else:
                # logger.info("✓ All upcoming events already have reminders scheduled")
                pass
            """
            # Show currently scheduled reminders
            scheduled = reminder_service.get_scheduled_reminders()
            
            if scheduled:
                # logger.info(f"\nCurrently scheduled reminders: {len(scheduled)}")
                for reminder in scheduled[:5]:  # Show first 5
                    # logger.info(f"   • {reminder['event_title']} - {reminder['reminder_label']} before")
                if len(scheduled) > 5:
                    # logger.info(f"   ... and {len(scheduled) - 5} more")
            else:
                # logger.info(f"\nNo reminders currently scheduled")
                pass

            # logger.info("=" * 80 + "\n")
            """
        except Exception as e:
            logger.error(f"Error in check_and_schedule_reminders: {e}")

    async def start(self, db):
        """Start the background monitoring task"""
        if not self.running:
            self.task = asyncio.create_task(self.monitor_calendar(db))
            logger.info("Background monitoring task created")

    async def stop(self):
        """Stop the background monitoring task"""
        if self.running:
            self.running = False
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            logger.info("Background monitoring stopped")


# Singleton instance
background_monitor = BackgroundMonitor()
