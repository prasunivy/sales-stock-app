import os
from supabase import create_client
import streamlit as st

# Get credentials from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

# If environment variables not available, try Streamlit secrets
if not SUPABASE_URL:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL")
if not SUPABASE_SERVICE_KEY:
    SUPABASE_SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_ANON_KEY:
    SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY")

# Create admin client (with service role key - full access)
admin_supabase = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    admin_supabase = create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_KEY
    )

# Create regular client (with anon key - user-level access)
supabase = None
if SUPABASE_URL and SUPABASE_ANON_KEY:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY
    )


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
