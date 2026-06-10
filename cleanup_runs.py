"""Delete bad scrape runs and all their child rows from Supabase."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

BAD_RUN_IDS = [1, 2, 3]

for rid in BAD_RUN_IDS:
    # Child rows cascade-delete automatically (ON DELETE CASCADE in schema)
    r = sb.table("scrape_runs").delete().eq("id", rid).execute()
    print(f"Deleted run #{rid}: {r.data}")

print("\nDone. Remaining runs:")
rows = sb.table("scrape_runs").select("*").order("id").execute()
for row in rows.data:
    print(f"  #{row['id']}  status={row['status']}  started={row['started_at']}")
