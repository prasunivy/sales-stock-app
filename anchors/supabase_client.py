import os
import time
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


# Errors that are transient and safe to retry
_RETRY_SIGNALS = (
    "resource temporarily unavailable",
    "errno 11",
    "connection reset",
    "connection refused",
    "broken pipe",
    "timed out",
    "timeout",
    "readtimeout",
    "remotedisconnected",
    "ssl",
)

_MAX_RETRIES  = 3
_RETRY_DELAYS = [0.5, 1.5, 3.0]   # seconds between retries


def safe_exec(q, msg="Database error"):
    """
    Safely execute a Supabase query with automatic retry for transient
    network errors (e.g. 'Resource temporarily unavailable', errno 11).

    Returns data list or empty list on error.
    Stops the app with an error message only after all retries are exhausted.
    """
    last_exc = None

    for attempt in range(_MAX_RETRIES):
        try:
            res = q.execute()

            if hasattr(res, "error") and res.error:
                st.error(msg)
                st.stop()

            return res.data or []

        except Exception as e:
            err_lower = str(e).lower()
            is_transient = any(sig in err_lower for sig in _RETRY_SIGNALS)

            if is_transient and attempt < _MAX_RETRIES - 1:
                # Wait then retry
                time.sleep(_RETRY_DELAYS[attempt])
                last_exc = e
                continue

            # Not transient, or final attempt — surface the error
            st.error(msg)
            st.exception(e)
            st.stop()

    # Should not reach here, but just in case
    if last_exc:
        st.error(msg)
        st.exception(last_exc)
        st.stop()

    return []
