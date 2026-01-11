"""Delete CSL7510 VCC calendar and recreate clean"""
from src.config import Config
import caldav

# Connect to CalDAV
client = caldav.DAVClient(
    url=Config.CALDAV_URL,
    username=Config.APPLE_USERNAME,
    password=Config.APPLE_PASSWORD
)

principal = client.principal()
calendars = principal.calendars()

print("\nDeleting CSL7510 VCC calendar...")

for cal in calendars:
    try:
        if cal.name == "CSL7510 VCC":
            cal.delete()
            print("✅ Deleted CSL7510 VCC")
            break
    except Exception as e:
        print(f"Error: {e}")

print("\nCalendar will be recreated on next sync with VEVENT support")
