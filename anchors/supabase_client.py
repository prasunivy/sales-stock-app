import os
from supabase import create_client

SUPABASE_URL = os.environ.get("https://uidjjsrxhknnnlymchke.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVpZGpqc3J4aGtubm5seW1jaGtlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTc5MzQwMywiZXhwIjoyMDgxMzY5NDAzfQ.d55jBzb-DV1IA0Z5oW6cLu1Fv6MOCU5LVXXd_mDU6xw")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Supabase environment variables not set")

admin_supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)
