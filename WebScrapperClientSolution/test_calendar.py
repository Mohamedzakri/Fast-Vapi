import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.calendar_service import calendar_service
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def test_calendar():
    """Test Google Calendar connection and fetch recent events"""
    print("\n" + "=" * 80)
    print("TESTING GOOGLE CALENDAR CONNECTION")
    print("=" * 80 + "\n")

    try:
        # Test: Get recent events
        print("📅 Fetching recent events from your calendar...\n")
        events = calendar_service.get_recent_events(max_results=5)

        if not events:
            print("📭 No events found in the last hour.")
            print("💡 Tip: Create a test event in your Google Calendar to see this work!\n")
        else:
            print(f"✅ Found {len(events)} event(s):\n")

            for i, event in enumerate(events, 1):
                formatted = calendar_service.format_event_log(event)
                print(f"Event {i}:")
                print(f"  Title: {formatted['title']}")
                print(f"  Start: {formatted['start_time']}")
                print(f"  End: {formatted['end_time']}")
                print(f"  Creator: {formatted['creator']}")
                print()

        print("=" * 80)
        print("✅ CALENDAR CONNECTION TEST SUCCESSFUL!")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        raise


if __name__ == "__main__":
    test_calendar()
