import os
import streamlit as st
from supabase import create_client

# Get credentials from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

# Fallback to Streamlit secrets if env vars not available
if not SUPABASE_URL and hasattr(st, 'secrets'):
    SUPABASE_URL = st.secrets.get("SUPABASE_URL")
if not SUPABASE_SERVICE_KEY and hasattr(st, 'secrets'):
    SUPABASE_SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_ANON_KEY and hasattr(st, 'secrets'):
    SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY")

# Create admin client (service role - full access)
admin_supabase = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    admin_supabase = create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY
    )

# Create regular client (anon key - user-level access)
supabase = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY
    )
elif SUPABASE_URL and SUPABASE_SERVICE_KEY:
    # Fallback: use admin client if anon key not available
    supabase = admin_supabase


def safe_exec(q, msg="Database error"):
    """
    Safely execute Supabase query with error handling
    Returns data or empty list on error
    """
    try:
        res = q.execute()
    except Exception as e:
        st.error(msg)
        st.exception(e)
        st.stop()

    if hasattr(res, "error") and res.error:
        st.error(msg)
        st.stop()

    return res.data or []
