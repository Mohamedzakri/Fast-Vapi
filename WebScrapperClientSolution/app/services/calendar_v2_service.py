import os
import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class CalendarV2Service:
    """Service for interacting with Google Calendar API"""

    def __init__(self):
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize the Google Calendar API service"""
        try:
            creds = None

            # Token.json stores the user's access and refresh tokens
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)

            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)

                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())

            self.service = build('calendar', 'v3', credentials=creds)
            logger.info("✅ Google Calendar service initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize Calendar service: {e}")
            raise

    def get_recent_events(self, max_results=10, hours_back=1):
        """
        Fetch recent events from Google Calendar

        Args:
            max_results: Maximum number of events to return
            hours_back: How many hours back to look for events

        Returns:
            List of event dictionaries
        """
        try:
            now = datetime.utcnow()
            time_min = (now - timedelta(hours=hours_back)).isoformat() + 'Z'

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            logger.info(f"📅 Fetched {len(events)} events from the last {hours_back} hour(s)")

            return events

        except HttpError as error:
            logger.error(f"❌ An error occurred: {error}")
            return []

    def get_upcoming_events(self, max_results=10, hours_ahead=24):
        """
        Fetch upcoming events from Google Calendar

        Args:
            max_results: Maximum number of events to return
            hours_ahead: How many hours ahead to look for events

        Returns:
            List of event dictionaries
        """
        try:
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(hours=hours_ahead)).isoformat() + 'Z'

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            logger.info(f"📅 Fetched {len(events)} upcoming events in the next {hours_ahead} hours")

            return events

        except HttpError as error:
            logger.error(f"❌ An error occurred: {error}")
            return []

    def get_event_by_id(self, event_id):
        """
        Fetch a specific event by ID

        Args:
            event_id: The event ID to fetch

        Returns:
            Event dictionary or None
        """
        try:
            event = self.service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()

            return event

        except HttpError as error:
            logger.error(f"❌ Error fetching event {event_id}: {error}")
            return None

    def format_event_log(self, event):
        """Format event data for logging"""
        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'N/A'))
        end = event.get('end', {}).get('dateTime', event.get('end', {}).get('date', 'N/A'))

        return {
            'id': event.get('id'),
            'title': event.get('summary', 'No Title'),
            'start_time': start,
            'end_time': end,
            'creator': event.get('creator', {}).get('email', 'Unknown'),
            'status': event.get('status', 'Unknown')
        }


# Create a singleton instance
calendar_v2_service = CalendarV2Service()