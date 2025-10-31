'''
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import os
import json

logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class CalendarService:
    """Service for Google Calendar integration with real-time monitoring"""

    def __init__(self):
        self.creds = None
        self.service = None
        self.last_checked = None
        self.monitored_events = set()  # Track event IDs we've already seen
        self.initialize_service()

    def initialize_service(self):
        """Initialize Google Calendar service with OAuth authentication"""
        try:
            # Token file stores the user's access and refresh tokens
            token_path = 'token.json'
            creds_path = 'credentials.json'

            if not os.path.exists(creds_path):
                logger.error("❌ credentials.json not found! Please add it to the project root.")
                raise FileNotFoundError(
                    "credentials.json not found. Please download it from Google Cloud Console."
                )

            # Load existing token if available
            if os.path.exists(token_path):
                self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)

            # If no valid credentials, let user log in
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("🔄 Refreshing expired credentials...")
                    self.creds.refresh(Request())
                else:
                    logger.info("🔐 Opening browser for Google Calendar authorization...")
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                    self.creds = flow.run_local_server(port=0)

                # Save credentials for next run
                with open(token_path, 'w') as token:
                    token.write(self.creds.to_json())
                logger.info("✅ Credentials saved")

            # Build the service
            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("✅ Google Calendar service initialized successfully")

            # Set initial last_checked time
            self.last_checked = datetime.utcnow()

        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Calendar service: {e}")
            raise

    def get_recent_events(
            self,
            max_results: int = 10,
            time_min: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent calendar events

        Args:
            max_results: Maximum number of events to return
            time_min: Get events created after this time (defaults to last check)

        Returns:
            List of calendar events
        """
        try:
            if not time_min:
                time_min = datetime.utcnow() - timedelta(hours=1)

            # Format time for API
            time_min_str = time_min.isoformat() + 'Z'

            logger.info(f"📅 Fetching events created after: {time_min_str}")

            # Call the Calendar API
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            logger.info(f"📊 Found {len(events)} events")

            return events

        except HttpError as error:
            logger.error(f"❌ Google Calendar API error: {error}")
            return []
        except Exception as e:
            logger.error(f"❌ Failed to fetch events: {e}")
            return []

    def detect_new_events(self) -> List[Dict[str, Any]]:
        """
        Detect events created since last check

        Returns:
            List of newly created events
        """
        try:
            if not self.last_checked:
                self.last_checked = datetime.utcnow() - timedelta(minutes=5)

            # Get events from last check time
            events = self.get_recent_events(
                max_results=50,
                time_min=self.last_checked
            )

            # Filter for truly new events (not seen before)
            new_events = []
            for event in events:
                event_id = event.get('id')

                # Check if this is a new event we haven't logged yet
                if event_id not in self.monitored_events:
                    # Check if event was created recently (within monitoring window)
                    created = event.get('created')
                    if created:
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        if created_dt.replace(tzinfo=None) >= self.last_checked:
                            new_events.append(event)
                            self.monitored_events.add(event_id)

            # Update last checked time
            self.last_checked = datetime.utcnow()

            if new_events:
                logger.info(f"🆕 Detected {len(new_events)} new event(s)!")

            return new_events

        except Exception as e:
            logger.error(f"❌ Error detecting new events: {e}")
            return []

    def format_event_log(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format event data for logging

        Args:
            event: Raw event data from Google Calendar API

        Returns:
            Formatted event information
        """
        # Extract key information
        event_id = event.get('id', 'N/A')
        summary = event.get('summary', 'No Title')

        # Handle start/end times
        start = event.get('start', {})
        end = event.get('end', {})

        start_time = start.get('dateTime', start.get('date', 'N/A'))
        end_time = end.get('dateTime', end.get('date', 'N/A'))

        # Parse creation time
        created = event.get('created', 'N/A')

        # Attendees
        attendees = event.get('attendees', [])
        attendee_emails = [a.get('email') for a in attendees if a.get('email')]

        formatted = {
            'event_id': event_id,
            'title': summary,
            'start_time': start_time,
            'end_time': end_time,
            'created_at': created,
            'location': event.get('location', 'N/A'),
            'description': event.get('description', 'N/A'),
            'attendees': attendee_emails,
            'creator': event.get('creator', {}).get('email', 'N/A'),
            'status': event.get('status', 'N/A'),
            'link': event.get('htmlLink', 'N/A')
        }

        return formatted

    def log_event_to_file(self, event: Dict[str, Any]):
        """
        Log event to text file and JSON file

        Args:
            event: Formatted event data
        """
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

            # Log to text file
            with open('calendar_events.log', 'a', encoding='utf-8') as f:
                f.write(f"\n{'=' * 80}\n")
                f.write(f"[{timestamp}] NEW EVENT CREATED\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Title: {event['title']}\n")
                f.write(f"Start: {event['start_time']}\n")
                f.write(f"End: {event['end_time']}\n")
                f.write(f"Created: {event['created_at']}\n")
                f.write(f"Creator: {event['creator']}\n")
                f.write(f"Location: {event['location']}\n")
                f.write(f"Status: {event['status']}\n")
                f.write(f"Link: {event['link']}\n")
                if event['attendees']:
                    f.write(f"Attendees: {', '.join(event['attendees'])}\n")
                f.write(f"{'=' * 80}\n\n")

            # Log to JSON file (append to array)
            json_file = 'calendar_events.json'
            events_list = []

            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    try:
                        events_list = json.load(f)
                    except json.JSONDecodeError:
                        events_list = []

            events_list.append({
                'logged_at': timestamp,
                **event
            })

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(events_list, f, indent=2, ensure_ascii=False)

            logger.info(f"📝 Event logged to files: {event['title']}")

        except Exception as e:
            logger.error(f"❌ Failed to log event to file: {e}")


# Singleton instance
calendar_service = CalendarService()
'''

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import logging
import uuid
import os
import json

logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


class CalendarService:
    """Service for Google Calendar integration with real-time monitoring"""

    def __init__(self):
        self.creds = None
        self.service = None
        self.last_checked = None
        self.monitored_events = set()  # Track event IDs we've already seen
        self.initialize_service()

    def initialize_service(self):
        """Initialize Google Calendar service with OAuth authentication"""
        try:
            # Token file stores the user's access and refresh tokens
            token_path = 'token.json'
            creds_path = 'credentials.json'

            if not os.path.exists(creds_path):
                logger.error("❌ credentials.json not found! Please add it to the project root.")
                raise FileNotFoundError(
                    "credentials.json not found. Please download it from Google Cloud Console."
                )

            # Load existing token if available
            if os.path.exists(token_path):
                self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)

            # If no valid credentials, let user log in
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("🔄 Refreshing expired credentials...")
                    self.creds.refresh(Request())
                else:
                    logger.info("🔐 Opening browser for Google Calendar authorization...")
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                    self.creds = flow.run_local_server(port=0)

                # Save credentials for next run
                with open(token_path, 'w') as token:
                    token.write(self.creds.to_json())
                logger.info("✅ Credentials saved")

            # Build the service
            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("✅ Google Calendar service initialized successfully")

            # Set initial last_checked time
            self.last_checked = datetime.utcnow()

        except Exception as e:
            logger.error(f"❌ Failed to initialize Google Calendar service: {e}")
            raise

    def get_recent_events(
            self,
            max_results: int = 10,
            time_min: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent calendar events

        Args:
            max_results: Maximum number of events to return
            time_min: Get events created after this time (defaults to last check)

        Returns:
            List of calendar events
        """
        try:
            if not time_min:
                time_min = datetime.utcnow() - timedelta(hours=1)

            # Format time for API
            time_min_str = time_min.isoformat() + 'Z'

            #logger.info(f"📅 Fetching events created after: {time_min_str}")

            # Call the Calendar API
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=time_min_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            logger.info(f"📊 Found {len(events)} events")

            return events

        except HttpError as error:
            logger.error(f"❌ Google Calendar API error: {error}")
            return []
        except Exception as e:
            logger.error(f"❌ Failed to fetch events: {e}")
            return []

    def detect_new_events(self) -> List[Dict[str, Any]]:
        """
        Detect events created since last check

        Returns:
            List of newly created events
        """
        try:
            if not self.last_checked:
                self.last_checked = datetime.utcnow() - timedelta(minutes=5)

            # Get events from last check time
            events = self.get_recent_events(
                max_results=50,
                time_min=self.last_checked
            )

            # Filter for truly new events (not seen before)
            new_events = []
            for event in events:
                event_id = event.get('id')

                # Check if this is a new event we haven't logged yet
                if event_id not in self.monitored_events:
                    # Check if event was created recently (within monitoring window)
                    created = event.get('created')
                    if created:
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        if created_dt.replace(tzinfo=None) >= self.last_checked:
                            new_events.append(event)
                            self.monitored_events.add(event_id)

            # Update last checked time
            self.last_checked = datetime.utcnow()

            if new_events:
                logger.info(f"🆕 Detected {len(new_events)} new event(s)!")

            return new_events

        except Exception as e:
            logger.error(f"❌ Error detecting new events: {e}")
            return []

    def format_event_log(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format event data for logging

        Args:
            event: Raw event data from Google Calendar API

        Returns:
            Formatted event information
        """
        # Extract key information
        event_id = event.get('id', 'N/A')
        summary = event.get('summary', 'No Title')

        # Handle start/end times
        start = event.get('start', {})
        end = event.get('end', {})

        start_time = start.get('dateTime', start.get('date', 'N/A'))
        end_time = end.get('dateTime', end.get('date', 'N/A'))

        # Parse creation time
        created = event.get('created', 'N/A')

        # Attendees
        attendees = event.get('attendees', [])
        attendee_emails = [a.get('email') for a in attendees if a.get('email')]

        formatted = {
            'event_id': event_id,
            'title': summary,
            'start_time': start_time,
            'end_time': end_time,
            'created_at': created,
            'location': event.get('location', 'N/A'),
            'description': event.get('description', 'N/A'),
            'attendees': attendee_emails,
            'creator': event.get('creator', {}).get('email', 'N/A'),
            'status': event.get('status', 'N/A'),
            'link': event.get('htmlLink', 'N/A')
        }

        return formatted

    def log_event_to_file(self, event: Dict[str, Any]):
        """
        Log event to text file and JSON file

        Args:
            event: Formatted event data
        """
        try:
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

            # Log to text file
            with open('calendar_events.log', 'a', encoding='utf-8') as f:
                f.write(f"\n{'=' * 80}\n")
                f.write(f"[{timestamp}] NEW EVENT CREATED\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Title: {event['title']}\n")
                f.write(f"Start: {event['start_time']}\n")
                f.write(f"End: {event['end_time']}\n")
                f.write(f"Created: {event['created_at']}\n")
                f.write(f"Creator: {event['creator']}\n")
                f.write(f"Location: {event['location']}\n")
                f.write(f"Status: {event['status']}\n")
                f.write(f"Link: {event['link']}\n")
                if event['attendees']:
                    f.write(f"Attendees: {', '.join(event['attendees'])}\n")
                f.write(f"{'=' * 80}\n\n")

            # Log to JSON file (append to array)
            json_file = 'calendar_events.json'
            events_list = []

            if os.path.exists(json_file):
                with open(json_file, 'r', encoding='utf-8') as f:
                    try:
                        events_list = json.load(f)
                    except json.JSONDecodeError:
                        events_list = []

            events_list.append({
                'logged_at': timestamp,
                **event
            })

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(events_list, f, indent=2, ensure_ascii=False)

            logger.info(f"📝 Event logged to files: {event['title']}")

        except Exception as e:
            logger.error(f"❌ Failed to log event to file: {e}")

            def create_webhook_channel(self, webhook_url: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
                """
                Register a webhook with Google Calendar to receive push notifications

                Args:
                    webhook_url: Your public webhook URL (from ngrok)
                    channel_id: Optional custom channel ID (auto-generated if not provided)

                Returns:
                    Channel information
                """
                try:
                    if not channel_id:
                        channel_id = str(uuid.uuid4())

                    # Create the watch request
                    body = {
                        'id': channel_id,
                        'type': 'web_hook',
                        'address': webhook_url,
                        'expiration': None  # Optional: set expiration time (Unix timestamp in milliseconds)
                    }

                    logger.info(f"🔗 Registering webhook with Google Calendar...")
                    logger.info(f"📍 Webhook URL: {webhook_url}")
                    logger.info(f"🆔 Channel ID: {channel_id}")

                    # Call the watch endpoint
                    watch_response = self.service.events().watch(
                        calendarId='primary',
                        body=body
                    ).execute()

                    logger.info("=" * 80)
                    logger.info("✅ WEBHOOK REGISTERED SUCCESSFULLY!")
                    logger.info(f"🆔 Channel ID: {watch_response.get('id')}")
                    logger.info(f"🔗 Resource ID: {watch_response.get('resourceId')}")
                    logger.info(f"⏰ Expiration: {watch_response.get('expiration', 'No expiration')}")
                    logger.info("=" * 80)

                    return watch_response

                except Exception as e:
                    logger.error(f"❌ Failed to register webhook: {e}")
                    raise Exception(f"Webhook registration failed: {str(e)}")

            def stop_webhook_channel(self, channel_id: str, resource_id: str):
                """
                Stop receiving webhook notifications

                Args:
                    channel_id: The channel ID to stop
                    resource_id: The resource ID from the watch response
                """
                try:
                    body = {
                        'id': channel_id,
                        'resourceId': resource_id
                    }

                    self.service.channels().stop(body=body).execute()

                    logger.info(f"🛑 Webhook channel stopped: {channel_id}")

                except Exception as e:
                    logger.error(f"❌ Failed to stop webhook: {e}")
                    raise Exception(f"Failed to stop webhook: {str(e)}")

    def create_webhook_channel(self, webhook_url: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a webhook with Google Calendar to receive push notifications

        Args:
            webhook_url: Your public webhook URL (from ngrok)
            channel_id: Optional custom channel ID (auto-generated if not provided)

        Returns:
            Channel information
        """
        try:
            if not channel_id:
                import uuid
                channel_id = str(uuid.uuid4())

            # Create the watch request
            body = {
                'id': channel_id,
                'type': 'web_hook',
                'address': webhook_url
            }

            logger.info(f"🔗 Registering webhook with Google Calendar...")
            logger.info(f"📍 Webhook URL: {webhook_url}")
            logger.info(f"🆔 Channel ID: {channel_id}")

            # Call the watch endpoint
            watch_response = self.service.events().watch(
                calendarId='primary',
                body=body
            ).execute()

            logger.info("=" * 80)
            logger.info("✅ WEBHOOK REGISTERED SUCCESSFULLY!")
            logger.info(f"🆔 Channel ID: {watch_response.get('id')}")
            logger.info(f"🔗 Resource ID: {watch_response.get('resourceId')}")
            logger.info(f"⏰ Expiration: {watch_response.get('expiration', 'No expiration')}")
            logger.info("=" * 80)

            return watch_response

        except Exception as e:
            logger.error(f"❌ Failed to register webhook: {e}")
            raise Exception(f"Webhook registration failed: {str(e)}")

    def stop_webhook_channel(self, channel_id: str, resource_id: str):
        """
        Stop receiving webhook notifications

        Args:
            channel_id: The channel ID to stop
            resource_id: The resource ID from the watch response
        """
        try:
            body = {
                'id': channel_id,
                'resourceId': resource_id
            }

            self.service.channels().stop(body=body).execute()

            logger.info(f"🛑 Webhook channel stopped: {channel_id}")

        except Exception as e:
            logger.error(f"❌ Failed to stop webhook: {e}")
            raise Exception(f"Failed to stop webhook: {str(e)}")

    def get_upcoming_events(self, days_ahead: int = 7, max_results: int = 50):
        """
        Get upcoming events for the next X days

        Args:
            days_ahead: Number of days to look ahead (default: 7)
            max_results: Maximum number of events to return (default: 50)

        Returns:
            List of upcoming events
        """
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            future = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + 'Z'

            #logger.info(f"📅 Fetching events from {now} to {future}")

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                timeMax=future,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            #logger.info(f"📊 Found {len(events)} upcoming event(s)")

            return events

        except Exception as e:
            logger.error(f"❌ Error fetching upcoming events: {e}")
            return []


# Singleton instance
calendar_service = CalendarService()
