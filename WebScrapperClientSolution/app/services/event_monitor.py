import asyncio
import logging
from datetime import datetime, timedelta
from typing import Set
from .calendar_v2_service import calendar_v2_service
from .new_event_notifier import new_event_notifier

logger = logging.getLogger(__name__)


class EventMonitor:
    """Monitor Google Calendar for newly created events"""

    def __init__(self):
        self.is_running = False
        self.check_interval = 60  # Check every 60 seconds
        self.known_event_ids: Set[str] = set()
        self._monitor_task = None
        logger.info("EventMonitor initialized")

    async def start(self):
        """Start monitoring for new events"""
        if self.is_running:
            logger.warning("EventMonitor is already running")
            return

        self.is_running = True
        logger.info("Starting EventMonitor...")

        # Initial load of existing events (so we don't notify for old events)
        await self._initialize_known_events()

        # Start the monitoring loop
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"EventMonitor started (checking every {self.check_interval}s)")

    async def stop(self):
        """Stop monitoring"""
        if not self.is_running:
            return

        logger.info("Stopping EventMonitor...")
        self.is_running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("EventMonitor stopped")

    async def _initialize_known_events(self):
        """Load existing events so we don't notify for them on startup"""
        try:
            logger.info("Loading existing events (to prevent initial spam)...")

            # Get events from the last 7 days and next 30 days
            events = calendar_v2_service.get_recent_events(max_results=100, hours_back=168)  # 7 days
            upcoming = calendar_v2_service.get_upcoming_events(max_results=100, hours_ahead=720)  # 30 days

            all_events = events + upcoming

            for event in all_events:
                event_id = event.get('id')
                if event_id:
                    self.known_event_ids.add(event_id)

            logger.info(f"Initialized with {len(self.known_event_ids)} existing events")

        except Exception as e:
            logger.error(f"Error initializing known events: {e}")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("EventMonitor loop started")

        while self.is_running:
            try:
                await self._check_for_new_events()
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                logger.info("Monitor loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.check_interval)  # Continue despite errors

    async def _check_for_new_events(self):
        """Check for new events and send notifications"""
        try:
            # Get events from the last hour and next 30 days
            recent_events = calendar_v2_service.get_recent_events(max_results=50, hours_back=1)
            upcoming_events = calendar_v2_service.get_upcoming_events(max_results=50, hours_ahead=720)

            all_events = recent_events + upcoming_events

            # Find new events
            new_events = []
            for event in all_events:
                event_id = event.get('id')
                if event_id and event_id not in self.known_event_ids:
                    new_events.append(event)
                    self.known_event_ids.add(event_id)

            # Notify for each new event
            if new_events:
                logger.info(f"🆕 Found {len(new_events)} new event(s)")

                for event in new_events:
                    try:
                        await new_event_notifier.notify_new_event(event)
                    except Exception as e:
                        logger.error(f"Error notifying for event {event.get('id')}: {e}")
            else:
                logger.debug("No new events found")

        except Exception as e:
            logger.error(f"Error checking for new events: {e}")


# Create singleton instance
event_monitor = EventMonitor()
