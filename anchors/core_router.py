import streamlit as st


def route_module():
    """
    Build the sidebar navigation and route to the active module.
    Also handles ?nav= URL parameter from mobile bottom nav bar.
    """
    # Handle mobile nav URL parameter
    params = st.query_params
    if "nav" in params:
        nav_val = params["nav"]
        if nav_val != st.session_state.get("active_module"):
            st.session_state.active_module = nav_val
            st.query_params.clear()
            st.rerun()

    role = st.session_state.get("role", "user")
    user = st.session_state.get("auth_user")

    # ── Sidebar header ────────────────────────────────────────────
    st.sidebar.title("📂 Ivy Pharmaceuticals")
    if user:
        from anchors.supabase_client import admin_supabase, safe_exec
        try:
            profile = safe_exec(
                admin_supabase.table("users")
                .select("username, designation")
                .eq("id", user.id)
                .limit(1),
                ""
            )
            if profile:
                st.sidebar.caption(
                    f"👤 {profile[0]['username']}  |  {profile[0].get('designation','')}"
                )
        except Exception:
            pass

    st.sidebar.divider()

    # ── Navigation buttons ────────────────────────────────────────
    st.sidebar.subheader("📋 Modules")

    # Statement (available to all, but sidebar logic differs by role)
    if st.sidebar.button("📦 Sales & Stock Statement", key="nav_statement"):
        _set_module("STATEMENT")

    # OPS
    if st.sidebar.button("📥 Orders / Purchase / Sales / Payment", key="nav_ops"):
        _set_module("OPS")

    # DCR
    if st.sidebar.button("📞 Daily Call Report", key="nav_dcr"):
        _set_module("DCR")

    # Doctor Fetch
    if st.sidebar.button("🔍 Doctor Fetch", key="nav_doctor_fetch"):
        _set_module("DOCTOR_FETCH")

    # Doctor I/O
    if st.sidebar.button("📊 Doctor Input / Output", key="nav_doctor_io"):
        _set_module("DOCTOR_IO")

    # Tour Programme
    if st.sidebar.button("🗓️ Tour Programme", key="nav_tour"):
        _set_module("TOUR")

    # POB
    if st.sidebar.button("📋 POB / Statement / Cr Nt", key="nav_pob"):
        _set_module("POB")

    # Reports (admin + managers)
    if role == "admin" or True:  # visible to all, data filtered by role inside
        if st.sidebar.button("📊 Reports & Analytics", key="nav_reports"):
            _set_module("REPORTS")

    # Admin-only section
    if role == "admin":
        st.sidebar.divider()
        st.sidebar.subheader("🔧 Admin")

        admin_items = {
            "nav_admin_statements": ("📄 Statements", "Statements"),
            "nav_admin_users":      ("👤 Users",      "Users"),
            "nav_admin_create_user":("➕ Create User", "Create User"),
            "nav_admin_stockists":  ("🏪 Stockists",  "Stockists"),
            "nav_admin_products":   ("📦 Products",   "Products"),
            "nav_admin_territories":("📍 Territories","Territories"),
            "nav_admin_reset_pwd":  ("🔐 Reset Password", "Reset User Password"),
            "nav_admin_audit":      ("📜 Audit Logs", "Audit Logs"),
            "nav_admin_lock":       ("🔒 Lock/Unlock Statements", "Lock / Unlock Statements"),
            "nav_admin_analytics":  ("📈 Analytics",  "Analytics"),
        }

        for key, (label, section) in admin_items.items():
            if st.sidebar.button(label, key=key):
                st.session_state.active_module = "ADMIN"
                st.session_state.admin_section = section
                # Clear statement engine when switching to admin panel
                for k in ["statement_id", "product_index", "statement_year",
                           "statement_month", "selected_stockist_id", "engine_stage"]:
                    st.session_state[k] = None
                st.rerun()

    # ── Route to module ───────────────────────────────────────────
    active = st.session_state.get("active_module")

    if active == "STATEMENT":
        from modules.statement.statement_main import run_statement
        run_statement()

    elif active == "OPS":
        from modules.ops.ops_main import run_ops
        run_ops()

    elif active == "DCR":
        from modules.dcr.dcr_main import run_dcr
        run_dcr()

    elif active == "DOCTOR_FETCH":
        from modules.dcr.doctor_fetch import run_doctor_fetch
        run_doctor_fetch()

    elif active == "DOCTOR_IO":
        from modules.dcr.doctor_io_main import run_doctor_io
        run_doctor_io()

    elif active == "TOUR":
        from modules.dcr.tour_programme import run_tour_programme
        run_tour_programme()

    elif active == "POB":
        from modules.pob.pob_main import run_pob
        run_pob()

    elif active == "REPORTS":
        from modules.statement.statement_main import run_reports
        run_reports()

    elif active == "ADMIN":
        from modules.statement.statement_main import run_admin_panel
        run_admin_panel()

    else:
        _show_home()


def _set_module(name):
    """Set active module and clear conflicting session state."""
    st.session_state.active_module = name
    # Clear statement engine state when switching away
    if name not in ("STATEMENT", "ADMIN"):
        for k in ["statement_id", "product_index", "statement_year",
                  "statement_month", "selected_stockist_id", "engine_stage"]:
            st.session_state[k] = None
    st.rerun()


def _show_home():
    st.title("🏠 Ivy Pharmaceuticals")
    st.markdown("""
    ### 👈 Select a module from the sidebar

    **Available Modules:**
    - 📦 **Sales & Stock Statement** — Enter monthly stock data for stockists
    - 📥 **Orders / Purchase / Sales / Payment** — Full OPS transaction management
    - 📞 **Daily Call Report** — Record doctor visits, gifts, expenses
    - 🔍 **Doctor Fetch** — Find and view doctor profiles
    - 📊 **Doctor Input / Output** — Track gifts given and sales output
    - 🗓️ **Tour Programme** — Plan and submit tour programmes for approval
    - 📋 **POB / Statement / Cr Nt** — Proof of Business documents
    - 📊 **Reports & Analytics** — Stock matrices, trend charts, forecasts
    """)
