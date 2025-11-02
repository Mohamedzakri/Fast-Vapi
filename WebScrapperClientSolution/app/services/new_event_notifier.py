import os
import logging
from datetime import datetime
from typing import Set
import json
from pathlib import Path
from dotenv import load_dotenv
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()
logger = logging.getLogger(__name__)


class NewEventNotifier:
    """Service for notifying about newly created calendar events"""

    def __init__(self):
        # Load configuration
        self.notification_mode = os.getenv('NEW_EVENT_NOTIFICATION_MODE', 'both')
        self.file_path = os.getenv('NEW_EVENT_NOTIFICATION_FILE', 'new_events.txt')

        # Email settings (reuse existing config)
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.receiver_email = os.getenv('RECEIVER_EMAIL')

        # Track processed events to prevent duplicates
        self.processed_events: Set[str] = set()
        self._load_processed_events()

        logger.info(f"NewEventNotifier initialized (mode: {self.notification_mode})")

    def _load_processed_events(self):
        """Load previously processed event IDs from file"""
        processed_file = Path('processed_events.json')
        if processed_file.exists():
            try:
                with open(processed_file, 'r') as f:
                    data = json.load(f)
                    self.processed_events = set(data.get('event_ids', []))
                logger.info(f"Loaded {len(self.processed_events)} processed event IDs")
            except Exception as e:
                logger.warning(f"Could not load processed events: {e}")

    def _save_processed_event(self, event_id: str):
        """Save a newly processed event ID to file"""
        self.processed_events.add(event_id)
        processed_file = Path('processed_events.json')
        try:
            with open(processed_file, 'w') as f:
                json.dump({'event_ids': list(self.processed_events)}, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save processed event: {e}")

    def has_been_processed(self, event_id: str) -> bool:
        """Check if an event has already been notified"""
        return event_id in self.processed_events

    async def notify_new_event(self, event: dict):
        """
        Send notification for a newly created calendar event

        Args:
            event: Google Calendar event dictionary
        """
        event_id = event.get('id')

        # Prevent duplicates
        if self.has_been_processed(event_id):
            logger.debug(f"Event {event_id} already processed, skipping")
            return

        event_summary = event.get('summary', 'No Title')
        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'N/A'))
        end = event.get('end', {}).get('dateTime', event.get('end', {}).get('date', 'N/A'))
        creator = event.get('creator', {}).get('email', 'Unknown')

        logger.info(f"Processing new event notification: {event_summary}")

        # Send notifications based on mode
        success = True

        if self.notification_mode in ['file', 'both']:
            success = success and self._write_to_file(event_id, event_summary, start, end, creator)

        if self.notification_mode in ['email', 'both']:
            success = success and await self._send_email(event_id, event_summary, start, end, creator)

        # Mark as processed only if notification succeeded
        if success:
            self._save_processed_event(event_id)
            logger.info(f"Successfully notified for event: {event_summary}")
        else:
            logger.error(f"Failed to send notifications for event: {event_summary}")

    def _write_to_file(self, event_id: str, title: str, start: str, end: str, creator: str) -> bool:
        """Write notification to text file"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            notification_text = f"""
{'=' * 80}
NEW CALENDAR EVENT CREATED
{'=' * 80}
Timestamp:    {timestamp}
Event ID:     {event_id}
Title:        {title}
Start Time:   {start}
End Time:     {end}
Created By:   {creator}
{'=' * 80}

"""

            # Append to file
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(notification_text)

            logger.info(f"Written notification to file: {self.file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to write to file: {e}")
            return False

    async def _send_email(self, event_id: str, title: str, start: str, end: str, creator: str) -> bool:
        """Send email notification for new event"""
        try:
            # Create email message
            message = MIMEMultipart('alternative')
            message['Subject'] = f"New Calendar Event: {title}"
            message['From'] = self.sender_email
            message['To'] = self.receiver_email

            # Create HTML email body
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="background-color: #4CAF50; color: white; padding: 15px; border-radius: 5px;">
                    <h2 style="margin: 0;">New Calendar Event Created</h2>
                </div>

                <div style="margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px;">
                    <p><strong>Event Title:</strong> {title}</p>
                    <p><strong>Start Time:</strong> {start}</p>
                    <p><strong>End Time:</strong> {end}</p>
                    <p><strong>Created By:</strong> {creator}</p>
                    <p><strong>Event ID:</strong> {event_id}</p>
                </div>

                <div style="margin-top: 20px; padding: 10px; background-color: #e3f2fd; border-left: 4px solid #2196F3; border-radius: 3px;">
                    <p style="margin: 0;"><strong>Note:</strong> This is a notification for a newly created event. You will receive separate reminders before the event starts.</p>
                </div>
            </body>
            </html>
            """

            # Plain text alternative
            text_body = f"""
NEW CALENDAR EVENT CREATED

Event Title: {title}
Start Time: {start}
End Time: {end}
Created By: {creator}
Event ID: {event_id}

Note: This is a notification for a newly created event. You will receive separate reminders before the event starts.
            """

            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            message.attach(part1)
            message.attach(part2)

            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                start_tls=True,
                username=self.sender_email,
                password=self.sender_password,
            )

            logger.info(f"Sent new-event email to {self.receiver_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


# Create singleton instance
new_event_notifier = NewEventNotifier()
