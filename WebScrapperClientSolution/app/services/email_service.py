import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications"""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.receiver_email = os.getenv("RECEIVER_EMAIL")

    async def send_reminder_email(
            self,
            event_title: str,
            event_start: str,
            reminder_time: str,
            event_link: Optional[str] = None
    ) -> bool:
        """
        Send a reminder email for an upcoming event

        Args:
            event_title: Title of the event
            event_start: Start time of the event
            reminder_time: How much time before event (e.g., "24 hours")
            event_link: Optional link to the event

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = f" Reminder: {event_title}"
            message["From"] = self.sender_email
            message["To"] = self.receiver_email

            # Create email body
            text_content = f"""
Event Reminder
{'=' * 50}

Event: {event_title}
Start Time: {event_start}
Reminder: {reminder_time} before event

{f'Event Link: {event_link}' if event_link else ''}

This is an automated reminder from your Calendar Notification System.
"""

            html_content = f"""
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 2px solid #4CAF50; border-radius: 10px;">
      <h2 style="color: #4CAF50; text-align: center;">⏰ Event Reminder</h2>
      <hr style="border: 1px solid #4CAF50;">

      <p><strong>Event:</strong> {event_title}</p>
      <p><strong>Start Time:</strong> {event_start}</p>
      <p><strong>Reminder:</strong> {reminder_time} before event</p>

      {f'<p><a href="{event_link}" style="color: #4CAF50; text-decoration: none;">View Event in Calendar →</a></p>' if event_link else ''}

      <hr style="border: 1px solid #eee; margin-top: 20px;">
      <p style="font-size: 12px; color: #666; text-align: center;">
        This is an automated reminder from your Calendar Notification System.
      </p>
    </div>
  </body>
</html>
"""

            # Attach both plain text and HTML versions
            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            message.attach(part1)
            message.attach(part2)

            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.sender_email,
                password=self.sender_password,
                start_tls=True
            )

            logger.info(f"Email sent successfully: {event_title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False


# Singleton instance
email_service = EmailService()
