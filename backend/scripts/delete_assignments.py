"""Delete all assignments to force recreation as calendar events"""
from src.database.db import Database

db = Database()

# Delete all assignments
db.client.table('assignments').delete().neq('id', 'xxx').execute()

print("✅ Deleted all assignments - sync will recreate them as calendar events")
