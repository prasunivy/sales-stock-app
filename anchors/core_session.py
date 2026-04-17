import streamlit as st
from datetime import datetime


def init_session():
    """Initialize all session state keys used across all modules."""
    defaults = {
        # Auth
        "auth_user": None,
        "role": None,
        # Active module routing
        "active_module": None,
        # Statement engine (from original app.py)
        "statement_id": None,
        "product_index": None,
        "statement_year": None,
        "statement_month": None,
        "selected_stockist_id": None,
        "engine_stage": None,
        "admin_section": None,
        # DCR
        "dcr_report_id": None,
        "dcr_current_step": 1,
        "dcr_user_id": None,
        "dcr_report_date": None,
        "dcr_area_type": None,
        "dcr_territory_ids": [],
        "dcr_submit_done": False,
        "dcr_delete_confirm": False,
        "dcr_home_action": None,
        "dcr_masters_mode": None,
        # Tour
        "tour_action": None,
        "selected_tour_id": None,
        # POB
        "pob_step": None,
        "pob_doc_id": None,
        # Doctor I/O
        "doctor_io_tab": None,
        # Drilldown (reports)
        "drilldown_product": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _try_restore_session():
    """
    If session state was wiped (after Streamlit reconnect/sleep),
    try to restore login silently using the username stored in the URL query params.
    Returns True if session was restored, False otherwise.
    """
    # Only attempt restore if not already logged in
    if st.session_state.get("auth_user"):
        return True

    # Check if username is stored in URL
    params = st.query_params
    username = params.get("u", None)
    if not username:
        return False

    try:
        from anchors.supabase_client import admin_supabase, supabase, safe_exec

        # Re-verify the user is still valid and active in Supabase
        user_check = safe_exec(
            admin_supabase.table("users")
            .select("id, is_active, role, username")
            .eq("username", username)
            .limit(1),
            "Error checking user"
        )

        if not user_check or not user_check[0]["is_active"]:
            # User no longer valid — clear the URL param and force re-login
            st.query_params.clear()
            return False

        # Re-authenticate silently using Supabase stored session
        # We use admin lookup to restore auth_user object
        user_row = user_check[0]

        # Create a minimal mock auth object so the app works normally
        class RestoredUser:
            def __init__(self, uid):
                self.id = uid

        st.session_state.auth_user = RestoredUser(user_row["id"])
        st.session_state.role = user_row["role"]

        # Reset engine state (safe defaults on reconnect)
        for k in ["engine_stage", "admin_section", "statement_id",
                  "product_index", "statement_year", "statement_month",
                  "selected_stockist_id", "active_module"]:
            st.session_state[k] = None

        return True

    except Exception:
        # If anything fails, fall back to login screen
        st.query_params.clear()
        return False


def handle_login():
    """Handle authentication. Shows login form if not authenticated."""
    init_session()

    # ── Try auto-restore from URL param first ─────────────────────
    if _try_restore_session():
        return  # Already logged in or just restored

    # ── Login screen ──────────────────────────────────────────────
    st.title("🏠 Ivy Pharmaceuticals")
    st.caption("Sales & Stock Management System")
    st.divider()
    st.subheader("🔐 Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", type="primary")

        if submit:
            if not username or not password:
                st.error("Please enter username and password")
            else:
                try:
                    from anchors.supabase_client import supabase, admin_supabase, safe_exec

                    user_check = safe_exec(
                        admin_supabase.table("users")
                        .select("id, is_active, role")
                        .eq("username", username)
                        .limit(1),
                        "Error checking user"
                    )

                    if not user_check or not user_check[0]["is_active"]:
                        st.error("❌ Invalid or inactive user")
                        st.stop()

                    email = f"{username}@internal.local"

                    auth_response = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })

                    # Store auth
                    st.session_state.auth_user = auth_response.user
                    st.session_state.role = user_check[0]["role"]

                    # ── Save username to URL so session can be restored ──
                    st.query_params["u"] = username

                    # Reset all engine state on fresh login
                    for k in ["engine_stage", "admin_section", "statement_id",
                               "product_index", "statement_year", "statement_month",
                               "selected_stockist_id", "active_module"]:
                        st.session_state[k] = None

                    st.success(f"✅ Welcome, {username}!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Login failed: {str(e)}")

    st.stop()
