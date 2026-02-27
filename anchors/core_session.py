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


def handle_login():
    """Handle authentication. Shows login form if not authenticated."""
    init_session()

    if st.session_state.auth_user:
        _show_logout_button()
        return

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


def _show_logout_button():
    """Render logout button in sidebar with statement lock-release."""
    if st.sidebar.button("🚪 Logout", key="logout_btn"):
        try:
            from anchors.supabase_client import admin_supabase

            # Release statement edit lock if held
            if st.session_state.get("statement_id") and st.session_state.get("auth_user"):
                user_id = st.session_state.auth_user.id
                admin_supabase.table("statements").update({
                    "editing_by": None,
                    "editing_at": None,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", st.session_state.statement_id)\
                  .eq("editing_by", user_id).execute()
        except Exception:
            pass  # Don't block logout on error

        st.session_state.clear()
        st.rerun()
