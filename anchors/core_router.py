import streamlit as st
from datetime import datetime


def route_module():
    """
    Top navigation bar — works on mobile and desktop.
    Replaces the sidebar completely.
    """
    role = st.session_state.get("role", "user")
    user = st.session_state.get("auth_user")

    # ── Get username ──────────────────────────────────────────────
    username = ""
    if user:
        try:
            from anchors.supabase_client import admin_supabase, safe_exec
            profile = safe_exec(
                admin_supabase.table("users")
                .select("username, designation")
                .eq("id", user.id)
                .limit(1), ""
            )
            if profile:
                username = profile[0].get("username", "")
        except Exception:
            pass

    # ── Top header bar ────────────────────────────────────────────
    st.markdown(f"""
    <div class="ivy-topnav">
        <div class="ivy-topnav-header">
            <div class="app-title">🌿 Ivy Pharmaceuticals</div>
            <div class="user-info">👤 {username} &nbsp;|&nbsp; {role.upper()}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Navigation buttons row ────────────────────────────────────
    st.markdown('<div class="ivy-topnav-buttons">', unsafe_allow_html=True)

    nav_items = [
        ("📦 Statement",   "STATEMENT"),
        ("📥 OPS",          "OPS"),
        ("📞 DCR",          "DCR"),
        ("🔍 Doctor Fetch", "DOCTOR_FETCH"),
        ("📊 Doc I/O",      "DOCTOR_IO"),
        ("🗓️ Tour",         "TOUR"),
        ("📋 POB",          "POB"),
        ("📈 Reports",      "REPORTS"),
    ]

    # Admin extra items
    admin_items = [
        ("📄 Statements",        "Statements"),
        ("👤 Users",             "Users"),
        ("➕ Create User",       "Create User"),
        ("🏪 Stockists",         "Stockists"),
        ("📦 Products",          "Products"),
        ("📍 Territories",       "Territories"),
        ("🔐 Reset Password",    "Reset User Password"),
        ("📜 Audit Logs",        "Audit Logs"),
        ("🔒 Lock/Unlock",       "Lock / Unlock Statements"),
        ("📈 Analytics",         "Analytics"),
    ]

    # Render module buttons in one scrollable row
    cols = st.columns(len(nav_items) + (1 if role == "admin" else 0) + 1)

    for i, (label, module) in enumerate(nav_items):
        with cols[i]:
            if st.button(label, key=f"nav_{module}"):
                _set_module(module)

    # Admin dropdown
    if role == "admin":
        with cols[len(nav_items)]:
            if st.button("🔧 Admin", key="nav_admin_toggle"):
                current = st.session_state.get("show_admin_menu", False)
                st.session_state.show_admin_menu = not current
                st.rerun()

    # Logout button — last column
    with cols[-1]:
        st.markdown('<div class="ivy-topnav-logout">', unsafe_allow_html=True)
        if st.button("🚪 Logout", key="logout_btn"):
            _do_logout()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Admin submenu ─────────────────────────────────────────────
    if role == "admin" and st.session_state.get("show_admin_menu"):
        with st.expander("🔧 Admin Panel — Select Section", expanded=True):
            a_cols = st.columns(5)
            for i, (label, section) in enumerate(admin_items):
                with a_cols[i % 5]:
                    if st.button(label, key=f"admin_sec_{section}"):
                        st.session_state.active_module = "ADMIN"
                        st.session_state.admin_section = section
                        st.session_state.show_admin_menu = False
                        for k in ["statement_id", "product_index", "statement_year",
                                  "statement_month", "selected_stockist_id", "engine_stage"]:
                            st.session_state[k] = None
                        st.rerun()

    st.divider()

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
        _show_home(username, role)


def _set_module(name):
    st.session_state.active_module = name
    st.session_state.show_admin_menu = False
    if name not in ("STATEMENT", "ADMIN"):
        for k in ["statement_id", "product_index", "statement_year",
                  "statement_month", "selected_stockist_id", "engine_stage"]:
            st.session_state[k] = None
    st.rerun()


def _do_logout():
    try:
        from anchors.supabase_client import admin_supabase
        if st.session_state.get("statement_id") and st.session_state.get("auth_user"):
            user_id = st.session_state.auth_user.id
            admin_supabase.table("statements").update({
                "editing_by": None,
                "editing_at": None,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", st.session_state.statement_id)\
              .eq("editing_by", user_id).execute()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()


def _show_home(username="", role=""):
    st.title("🏠 Welcome to Ivy Pharmaceuticals")
    st.markdown(f"**Logged in as:** {username} ({role})")
    st.markdown("""
    ### 👆 Select a module from the navigation bar above

    | Module | Description |
    |--------|-------------|
    | 📦 Statement | Enter monthly stock data for stockists |
    | 📥 OPS | Orders, Purchase, Sales, Payments |
    | 📞 DCR | Daily Call Report — doctor visits |
    | 🔍 Doctor Fetch | Find and view doctor profiles |
    | 📊 Doc I/O | Doctor Input / Output tracking |
    | 🗓️ Tour | Tour Programme planning |
    | 📋 POB | Proof of Business documents |
    | 📈 Reports | Stock matrices, analytics, forecasts |
    """)
