from fastapi import APIRouter, HTTPException, status, Request, BackgroundTasks
from app.services import calendar_service, DatabaseService
from app.config.database import get_database
from typing import Optional
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/calendar",
    tags=["calendar"]
)


@router.get("/events", summary="Get recent calendar events")
async def get_recent_events(limit: int = 10):
    """
    Get recent calendar events

    - **limit**: Maximum number of events to return (default: 10, max: 50)
    """
    try:
        if limit > 50:
            limit = 50

        logger.info(f"📅 Fetching {limit} recent events")

        events = calendar_service.get_recent_events(max_results=limit)

        # Format events for response
        formatted_events = [
            calendar_service.format_event_log(event)
            for event in events
        ]

        return {
            "success": True,
            "count": len(formatted_events),
            "events": formatted_events
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/detect-new", summary="Manually check for new events")
async def detect_new_events():
    """
    Manually trigger detection of new calendar events

    This endpoint checks for events created since the last check
    """
    try:
        logger.info("🔍 Manually checking for new events...")

        new_events = calendar_service.detect_new_events()

        if new_events:
            # Log each new event
            for event in new_events:
                formatted = calendar_service.format_event_log(event)

                # Log to console
                logger.info("=" * 80)
                logger.info("🆕 NEW EVENT DETECTED!")
                logger.info(f"📌 Title: {formatted['title']}")
                logger.info(f"🕐 Start: {formatted['start_time']}")
                logger.info(f"🕑 End: {formatted['end_time']}")
                logger.info(f"👤 Creator: {formatted['creator']}")
                logger.info("=" * 80)

                # Log to files
                calendar_service.log_event_to_file(formatted)

                # Optional: Save to MongoDB
                try:
                    db = get_database()
                    db_service = DatabaseService(db)

                    await db_service.db.calendar_events.insert_one({
                        **formatted,
                        'detected_at': datetime.utcnow(),
                        'source': 'manual_detection'
                    })
                    logger.info("💾 Event saved to MongoDB")
                except Exception as db_error:
                    logger.warning(f"⚠️ Could not save to MongoDB: {db_error}")

        return {
            "success": True,
            "new_events_count": len(new_events),
            "new_events": [
                calendar_service.format_event_log(event)
                for event in new_events
            ],
            "message": f"Found {len(new_events)} new event(s)" if new_events else "No new events"
        }

    except Exception as e:
        logger.error(f"❌ Failed to detect new events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/monitoring/start", summary="Start background monitoring")
async def start_background_monitoring():
    """
    Manually start background monitoring (if stopped)
    """
    try:
        from app.services.background_tasks import background_monitor
        from app.config.database import get_database

        if background_monitor.running:
            return {
                "success": False,
                "message": "Background monitoring is already running"
            }

        db = get_database()
        await background_monitor.start(db)

        return {
            "success": True,
            "message": "Background monitoring started",
            "check_interval": f"{background_monitor.check_interval} seconds"
        }

    except Exception as e:
        logger.error(f"❌ Failed to start monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/monitoring/stop", summary="Stop background monitoring")
async def stop_background_monitoring():
    """
    Stop background monitoring
    """
    try:
        from app.services.background_tasks import background_monitor

        if not background_monitor.running:
            return {
                "success": False,
                "message": "Background monitoring is not running"
            }

        await background_monitor.stop()

        return {
            "success": True,
            "message": "Background monitoring stopped"
        }

    except Exception as e:
        logger.error(f"❌ Failed to stop monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/monitoring/status", summary="Get background monitoring status")
async def get_background_monitoring_status():
    """
    Get the status of background monitoring
    """
    try:
        from app.services.background_tasks import background_monitor

        return {
            "success": True,
            "monitoring_active": background_monitor.running,
            "check_interval_seconds": background_monitor.check_interval,
            "last_checked": calendar_service.last_checked.isoformat() if calendar_service.last_checked else None,
            "events_monitored": len(calendar_service.monitored_events)
        }

    except Exception as e:
        logger.error(f"❌ Failed to get status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/reset-monitoring", summary="Reset event monitoring")
async def reset_monitoring():
    """
    Reset the monitoring state (clears monitored events set)

    Use this to start fresh detection
    """
    try:
        calendar_service.monitored_events.clear()
        calendar_service.last_checked = datetime.utcnow() - timedelta(minutes=5)

        logger.info("🔄 Monitoring state reset")

        return {
            "success": True,
            "message": "Monitoring reset. Will detect events from the last 5 minutes."
        }

    except Exception as e:
        logger.error(f"❌ Reset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/debug/all-events", summary="Debug: See all events with created times")
async def debug_all_events():
    """
    Debug endpoint to see all events and their creation times
    """
    try:
        events = calendar_service.get_recent_events(max_results=50)

        debug_info = []
        for event in events:
            formatted = calendar_service.format_event_log(event)
            debug_info.append({
                "title": formatted['title'],
                "start_time": formatted['start_time'],
                "created_at": formatted['created_at'],
                "event_id": formatted['event_id'],
                "already_monitored": formatted['event_id'] in calendar_service.monitored_events
            })

        return {
            "success": True,
            "total_events": len(events),
            "last_checked": calendar_service.last_checked.isoformat() if calendar_service.last_checked else None,
            "monitored_count": len(calendar_service.monitored_events),
            "events": debug_info
        }

    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/status", summary="Get monitoring status")
async def get_monitoring_status():
    """
    Get the current status of calendar monitoring
    """
    try:
        return {
            "success": True,
            "service": "Google Calendar Monitor",
            "status": "active",
            "last_checked": calendar_service.last_checked.isoformat() if calendar_service.last_checked else None,
            "monitored_events_count": len(calendar_service.monitored_events),
            "calendar_connected": calendar_service.service is not None
        }

    except Exception as e:
        logger.error(f"❌ Failed to get status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/webhook", summary="Google Calendar webhook endpoint")
async def calendar_webhook(request: Request):
    """
    Webhook endpoint for Google Calendar push notifications

    This endpoint receives notifications when calendar events change.
    Note: Requires webhook setup with Google Calendar API.
    """
    try:
        # Get headers
        headers = dict(request.headers)

        # Google Calendar sends these headers
        channel_id = headers.get('x-goog-channel-id')
        resource_id = headers.get('x-goog-resource-id')
        resource_state = headers.get('x-goog-resource-state')

        logger.info("=" * 80)
        logger.info("📨 WEBHOOK RECEIVED FROM GOOGLE CALENDAR")
        logger.info(f"Channel ID: {channel_id}")
        logger.info(f"Resource ID: {resource_id}")
        logger.info(f"State: {resource_state}")
        logger.info("=" * 80)

        # When we receive a webhook, check for new events
        if resource_state in ['exists', 'sync']:
            new_events = calendar_service.detect_new_events()

            if new_events:
                logger.info(f"🎉 Webhook triggered: {len(new_events)} new event(s) detected!")

                for event in new_events:
                    formatted = calendar_service.format_event_log(event)

                    # Log to console
                    logger.info("🆕 NEW EVENT FROM WEBHOOK!")
                    logger.info(f"📌 {formatted['title']}")
                    logger.info(f"🕐 {formatted['start_time']} - {formatted['end_time']}")

                    # Save to MongoDB
                    try:
                        db = get_database()
                        db_service = DatabaseService(db)

                        await db_service.db.calendar_events.insert_one({
                            **formatted,
                            'detected_at': datetime.utcnow(),
                            'source': 'webhook'
                        })
                    except Exception as db_error:
                        logger.warning(f"⚠️ Could not save to MongoDB: {db_error}")

        return {"success": True, "message": "Webhook received"}

    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/logs", summary="Get calendar event logs")
async def get_calendar_logs(limit: int = 20):
    """
    Get logged calendar events from MongoDB

    - **limit**: Maximum number of logs to return (default: 20, max: 100)
    """
    try:
        if limit > 100:
            limit = 100

        db = get_database()
        db_service = DatabaseService(db)

        # Get events from MongoDB
        cursor = db_service.db.calendar_events.find().sort("detected_at", -1).limit(limit)
        events = await cursor.to_list(length=limit)

        # Convert ObjectIds to strings
        for event in events:
            event['_id'] = str(event['_id'])

        return {
            "success": True,
            "count": len(events),
            "events": events
        }

    except Exception as e:
        logger.error(f"❌ Failed to get logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Store active webhook info (in production, use database)
active_webhook = {
    "channel_id": None,
    "resource_id": None,
    "webhook_url": None,
    "registered_at": None
}


@router.post("/webhook/register", summary="Register webhook with Google Calendar")
async def register_webhook(webhook_url: str):
    """
    Register a webhook to receive real-time notifications from Google Calendar

    - **webhook_url**: Your public webhook URL (e.g., from ngrok)

    Example: https://abc123.ngrok.io/api/v1/calendar/webhook
    """
    try:
        logger.info(f"📝 Registering webhook: {webhook_url}")

        # Register the webhook
        response = calendar_service.create_webhook_channel(webhook_url)

        # Store webhook info
        global active_webhook
        active_webhook = {
            "channel_id": response.get('id'),
            "resource_id": response.get('resourceId'),
            "webhook_url": webhook_url,
            "registered_at": datetime.utcnow().isoformat(),
            "expiration": response.get('expiration')
        }

        return {
            "success": True,
            "message": "Webhook registered successfully!",
            "webhook_info": active_webhook
        }

    except Exception as e:
        logger.error(f"❌ Failed to register webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/webhook/unregister", summary="Unregister webhook")
async def unregister_webhook():
    """
    Stop receiving webhook notifications from Google Calendar
    """
    try:
        global active_webhook

        if not active_webhook.get("channel_id"):
            return {
                "success": False,
                "message": "No active webhook to unregister"
            }

        # Stop the webhook
        calendar_service.stop_webhook_channel(
            active_webhook["channel_id"],
            active_webhook["resource_id"]
        )

        # Clear stored info
        old_webhook = active_webhook.copy()
        active_webhook = {
            "channel_id": None,
            "resource_id": None,
            "webhook_url": None,
            "registered_at": None
        }

        return {
            "success": True,
            "message": "Webhook unregistered successfully",
            "unregistered_webhook": old_webhook
        }

    except Exception as e:
        logger.error(f"❌ Failed to unregister webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/webhook/info", summary="Get active webhook info")
async def get_webhook_info():
    """
    Get information about the currently active webhook
    """
    return {
        "success": True,
        "active_webhook": active_webhook if active_webhook.get("channel_id") else None,
        "webhook_active": active_webhook.get("channel_id") is not None
    }
