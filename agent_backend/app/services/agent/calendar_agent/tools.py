import json
from typing import Optional

from langchain_core.tools import tool
from langchain.tools import ToolRuntime

from ....utils.logger import get_logger
from ..orchestrator_agent.dataClasses import Context

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_user_calendar_service(user_id: str):
    """Build a Google Calendar API client using the stored per-user OAuth token.

    Raises RuntimeError if the user has not connected Google Calendar.
    Auto-refreshes the access token when it has expired.
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError(
            "Google API client libraries are not installed. "
            "Run: pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from exc

    from ....db import SessionLocal
    from ....models.chat_models import UserGoogleToken
    from datetime import datetime

    db = SessionLocal()
    try:
        record = (
            db.query(UserGoogleToken)
            .filter_by(user_id=user_id, service="google_calendar")
            .first()
        )
        if not record:
            raise RuntimeError(
                "Google Calendar is not connected. "
                "Please connect your account under Settings → Integrations."
            )

        token_data = json.loads(record.token_json)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", SCOPES),
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_data["token"] = creds.token
            record.token_json = json.dumps(token_data)
            record.updated_at = datetime.utcnow()
            db.commit()
            logger.info("Refreshed Google Calendar token for user %s", user_id)

        return build("calendar", "v3", credentials=creds)
    finally:
        db.close()


def _format_event(event: dict) -> str:
    start = event.get("start", {})
    end = event.get("end", {})
    start_str = start.get("dateTime", start.get("date", "unknown"))
    end_str = end.get("dateTime", end.get("date", "unknown"))
    attendees = event.get("attendees", [])
    attendee_list = ", ".join(a.get("email", "") for a in attendees) if attendees else "none"
    return (
        f"ID: {event.get('id')}\n"
        f"Title: {event.get('summary', '(no title)')}\n"
        f"Start: {start_str}\n"
        f"End: {end_str}\n"
        f"Location: {event.get('location', 'none')}\n"
        f"Attendees: {attendee_list}\n"
        f"Description: {event.get('description', 'none')}\n"
        f"Status: {event.get('status', 'unknown')}\n"
        f"Link: {event.get('htmlLink', 'none')}"
    )


@tool(parse_docstring=True)
def list_calendars_tool(runtime: ToolRuntime[Context]) -> str:
    """List all Google Calendars accessible to the authenticated user.

    Args:
        runtime: Injected runtime providing user context.

    Returns:
        Formatted list of calendars with their IDs, names, and access roles.
    """
    try:
        user_id = runtime.context.user_id
        service = _get_user_calendar_service(user_id)
        result = service.calendarList().list().execute()
        items = result.get("items", [])
        if not items:
            return "No calendars found."
        lines = [f"Found {len(items)} calendar(s):\n"]
        for cal in items:
            lines.append(
                f"- ID: {cal['id']}\n"
                f"  Name: {cal.get('summary', '(no name)')}\n"
                f"  Access: {cal.get('accessRole', 'unknown')}\n"
                f"  Primary: {cal.get('primary', False)}"
            )
        return "\n".join(lines)
    except Exception as exc:
        logger.error("list_calendars_tool error: %s", exc)
        return f"Error listing calendars: {exc}"


@tool(parse_docstring=True)
def list_calendar_events_tool(
    time_min: str,
    time_max: str,
    runtime: ToolRuntime[Context],
    calendar_id: str = "primary",
    max_results: int = 20,
    query: str = "",
) -> str:
    """List events from a Google Calendar within a time range.

    Args:
        time_min: Start of the time range in RFC3339 format (e.g. '2025-01-01T00:00:00Z').
        time_max: End of the time range in RFC3339 format (e.g. '2025-01-31T23:59:59Z').
        runtime: Injected runtime providing user context.
        calendar_id: Calendar ID to query. Use 'primary' for the main calendar.
        max_results: Maximum number of events to return (default 20, max 250).
        query: Free-text search query to filter events by title or description.

    Returns:
        Formatted list of events with their IDs, titles, times, attendees, and links.
    """
    try:
        user_id = runtime.context.user_id
        service = _get_user_calendar_service(user_id)
        params = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": min(max_results, 250),
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if query:
            params["q"] = query

        result = service.events().list(**params).execute()
        events = result.get("items", [])
        if not events:
            return f"No events found in the specified range for calendar '{calendar_id}'."

        lines = [f"Found {len(events)} event(s):\n"]
        for event in events:
            lines.append(_format_event(event))
            lines.append("---")
        return "\n".join(lines)
    except Exception as exc:
        logger.error("list_calendar_events_tool error: %s", exc)
        return f"Error listing events: {exc}"


@tool(parse_docstring=True)
def get_calendar_event_tool(
    event_id: str,
    runtime: ToolRuntime[Context],
    calendar_id: str = "primary",
) -> str:
    """Retrieve full details of a specific Google Calendar event by its ID.

    Args:
        event_id: The unique ID of the event to retrieve.
        runtime: Injected runtime providing user context.
        calendar_id: Calendar ID that contains the event. Use 'primary' for the main calendar.

    Returns:
        Full event details including title, times, description, attendees, and link.
    """
    try:
        user_id = runtime.context.user_id
        service = _get_user_calendar_service(user_id)
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return _format_event(event)
    except Exception as exc:
        logger.error("get_calendar_event_tool error: %s", exc)
        return f"Error retrieving event '{event_id}': {exc}"


@tool(parse_docstring=True)
def create_calendar_event_tool(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    runtime: ToolRuntime[Context],
    calendar_id: str = "primary",
    description: str = "",
    location: str = "",
    attendees: str = "",
    timezone: str = "UTC",
) -> str:
    """Create a new event in a Google Calendar.

    Args:
        summary: Title of the event.
        start_datetime: Event start in RFC3339 format (e.g. '2025-06-15T10:00:00').
        end_datetime: Event end in RFC3339 format (e.g. '2025-06-15T11:00:00').
        runtime: Injected runtime providing user context.
        calendar_id: Calendar ID to create the event in. Use 'primary' for the main calendar.
        description: Optional description or notes for the event.
        location: Optional physical or virtual location.
        attendees: Comma-separated list of attendee email addresses (e.g. 'a@x.com,b@x.com').
        timezone: IANA timezone for the event (e.g. 'America/New_York'). Defaults to UTC.

    Returns:
        Confirmation with the new event ID and link, or an error message.
    """
    try:
        user_id = runtime.context.user_id
        service = _get_user_calendar_service(user_id)
        event_body: dict = {
            "summary": summary,
            "start": {"dateTime": start_datetime, "timeZone": timezone},
            "end": {"dateTime": end_datetime, "timeZone": timezone},
        }
        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [
                {"email": e.strip()} for e in attendees.split(",") if e.strip()
            ]

        created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return (
            f"Event created successfully.\n"
            f"ID: {created['id']}\n"
            f"Title: {created.get('summary')}\n"
            f"Start: {created['start'].get('dateTime', created['start'].get('date'))}\n"
            f"End: {created['end'].get('dateTime', created['end'].get('date'))}\n"
            f"Link: {created.get('htmlLink')}"
        )
    except Exception as exc:
        logger.error("create_calendar_event_tool error: %s", exc)
        return f"Error creating event: {exc}"


@tool(parse_docstring=True)
def update_calendar_event_tool(
    event_id: str,
    runtime: ToolRuntime[Context],
    calendar_id: str = "primary",
    summary: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
    description: str = "",
    location: str = "",
    timezone: str = "",
) -> str:
    """Update an existing Google Calendar event. Only provided fields are changed.

    Args:
        event_id: The ID of the event to update.
        runtime: Injected runtime providing user context.
        calendar_id: Calendar ID that contains the event. Use 'primary' for the main calendar.
        summary: New title for the event. Leave empty to keep current value.
        start_datetime: New start datetime in RFC3339 format. Leave empty to keep current value.
        end_datetime: New end datetime in RFC3339 format. Leave empty to keep current value.
        description: New description. Leave empty to keep current value.
        location: New location. Leave empty to keep current value.
        timezone: IANA timezone for updated start/end times. Leave empty to keep current timezone.

    Returns:
        Confirmation with updated event details, or an error message.
    """
    try:
        user_id = runtime.context.user_id
        service = _get_user_calendar_service(user_id)
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        if summary:
            event["summary"] = summary
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if start_datetime:
            tz = timezone or event["start"].get("timeZone", "UTC")
            event["start"] = {"dateTime": start_datetime, "timeZone": tz}
        if end_datetime:
            tz = timezone or event["end"].get("timeZone", "UTC")
            event["end"] = {"dateTime": end_datetime, "timeZone": tz}

        updated = (
            service.events()
            .update(calendarId=calendar_id, eventId=event_id, body=event)
            .execute()
        )
        return (
            f"Event updated successfully.\n"
            f"ID: {updated['id']}\n"
            f"Title: {updated.get('summary')}\n"
            f"Start: {updated['start'].get('dateTime', updated['start'].get('date'))}\n"
            f"End: {updated['end'].get('dateTime', updated['end'].get('date'))}\n"
            f"Link: {updated.get('htmlLink')}"
        )
    except Exception as exc:
        logger.error("update_calendar_event_tool error: %s", exc)
        return f"Error updating event '{event_id}': {exc}"


@tool(parse_docstring=True)
def delete_calendar_event_tool(
    event_id: str,
    runtime: ToolRuntime[Context],
    calendar_id: str = "primary",
) -> str:
    """Delete a Google Calendar event permanently.

    Args:
        event_id: The ID of the event to delete.
        runtime: Injected runtime providing user context.
        calendar_id: Calendar ID that contains the event. Use 'primary' for the main calendar.

    Returns:
        Confirmation that the event was deleted, or an error message.
    """
    try:
        user_id = runtime.context.user_id
        service = _get_user_calendar_service(user_id)
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return f"Event '{event_id}' deleted successfully from calendar '{calendar_id}'."
    except Exception as exc:
        logger.error("delete_calendar_event_tool error: %s", exc)
        return f"Error deleting event '{event_id}': {exc}"


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on calendar task progress and planning.

    Use this after retrieving calendar data to assess whether you have enough
    information to answer the user or need additional lookups.

    Args:
        reflection: Your detailed reflection on current findings and next steps.

    Returns:
        Confirmation that reflection was recorded.
    """
    return f"Reflection recorded: {reflection}"
