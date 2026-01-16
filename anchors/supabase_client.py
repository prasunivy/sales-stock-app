import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

admin_supabase = None

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    admin_supabase = create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY
    )
