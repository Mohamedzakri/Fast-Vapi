import asyncio
from datetime import datetime
import logging
from app.services.calendar_service import calendar_service
from app.services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class BackgroundMonitor:
    """Background task for monitoring Google Calendar events"""

    def __init__(self):
        self.running = False
        self.task = None
        self.check_interval = 3  # seconds
        self.db_service = None

    async def monitor_calendar(self, db):
        """
        Background task that continuously monitors calendar for new events

        Args:
            db: Database instance
        """
        self.running = True
        self.db_service = DatabaseService(db)

        logger.info("=" * 80)
        logger.info("🚀 BACKGROUND CALENDAR MONITORING STARTED")
        logger.info(f"⏱️  Checking every {self.check_interval} seconds")
        logger.info("=" * 80)

        while self.running:
            try:
                # Check for new events
                new_events = calendar_service.detect_new_events()

                if new_events:
                    logger.info("=" * 80)
                    logger.info(f"🎉 BACKGROUND DETECTION: Found {len(new_events)} new event(s)!")
                    logger.info("=" * 80)

                    for event in new_events:
                        formatted = calendar_service.format_event_log(event)

                        # Log to console
                        logger.info("🆕 NEW EVENT DETECTED (Background)")
                        logger.info(f"📌 Title: {formatted['title']}")
                        logger.info(f"🕐 Start: {formatted['start_time']}")
                        logger.info(f"🕑 End: {formatted['end_time']}")
                        logger.info(f"👤 Creator: {formatted['creator']}")
                        logger.info(f"🔗 Link: {formatted['link']}")
                        logger.info("-" * 80)

                        # Log to files
                        calendar_service.log_event_to_file(formatted)

                        # Save to MongoDB
                        try:
                            await self.db_service.db.calendar_events.insert_one({
                                **formatted,
                                'detected_at': datetime.utcnow(),
                                'source': 'background_polling'
                            })
                            logger.info("💾 Event saved to MongoDB")
                        except Exception as db_error:
                            logger.error(f"❌ MongoDB save failed: {db_error}")

                    logger.info("=" * 80)

                # Wait before next check
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"❌ Background monitoring error: {e}")
                await asyncio.sleep(self.check_interval)

    async def start(self, db):
        """Start the background monitoring task"""
        if not self.running:
            self.task = asyncio.create_task(self.monitor_calendar(db))
            logger.info("✅ Background monitoring task created")

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
            logger.info("🛑 Background monitoring stopped")


# Singleton instance
background_monitor = BackgroundMonitor()
