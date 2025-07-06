from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from config import CALENDER_ID
# === CONFIGURATION ===
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'credentials.json'  # Path to service account key
CALENDAR_ID =CALENDER_ID      # ✅ Replace with your Gmail calendar ID

def create_event(subject, chapter, topic, deadline_str, description):
    """
    Create a Google Calendar event for the assignment.
    Returns a public link to the event.
    """
    # Authenticate with service account
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=credentials)

    # Construct event details
    event = {
        'summary': f'Assignment: {subject} - {chapter} - {topic}',
        'description': description,
        'start': {
            'dateTime': deadline_str,
            'timeZone': 'Asia/Kolkata',
        },
        'end': {
            'dateTime': (datetime.fromisoformat(deadline_str) + timedelta(hours=1)).isoformat(),
            'timeZone': 'Asia/Kolkata',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 30}
            ],
        },
    }

    # Send to Google Calendar
    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')  # Link to view event
