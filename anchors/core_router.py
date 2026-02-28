import streamlit as st
from datetime import datetime


def route_module():
    """
    Navigation — green header bar + selectbox nav.
    Works perfectly on mobile and desktop.
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

    # ── Green header bar (pure HTML — always visible) ─────────────
    st.markdown(f"""
    <div style="
        background: #1a6b5a;
        color: white;
        padding: 0.55rem 1.2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-radius: 0 0 10px 10px;
        margin-bottom: 0.75rem;
        box-shadow: 0 2px 8px rgba(26,107,90,0.18);
    ">
        <div style="font-size:1rem; font-weight:700; letter-spacing:0.01em;">
            🌿 Ivy Pharmaceuticals
        </div>
        <div style="font-size:0.78rem; opacity:0.88;">
            👤 {username}&nbsp;&nbsp;|&nbsp;&nbsp;{role.upper()}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Nav + Logout in one row ───────────────────────────────────
    nav_col, logout_col = st.columns([5, 1])

    # Build module options
    nav_options = [
        "🏠 Home",
        "📦 Statement",
        "📥 OPS",
        "📞 DCR",
        "🔍 Doctor Fetch",
        "📊 Doc I/O",
        "🗓️ Tour",
        "📋 POB",
        "📈 Reports",
    ]
    if role == "admin":
        nav_options.append("🔧 Admin")

    # Map label → module key
    label_to_module = {
        "🏠 Home":          None,
        "📦 Statement":     "STATEMENT",
        "📥 OPS":           "OPS",
        "📞 DCR":           "DCR",
        "🔍 Doctor Fetch":  "DOCTOR_FETCH",
        "📊 Doc I/O":       "DOCTOR_IO",
        "🗓️ Tour":          "TOUR",
        "📋 POB":           "POB",
        "📈 Reports":       "REPORTS",
        "🔧 Admin":         "ADMIN",
    }

    # Find current selection label from active_module
    module_to_label = {v: k for k, v in label_to_module.items()}
    active = st.session_state.get("active_module")
    current_label = module_to_label.get(active, "🏠 Home")
    current_index = nav_options.index(current_label) if current_label in nav_options else 0

    with nav_col:
        selected_label = st.selectbox(
            "Navigate",
            nav_options,
            index=current_index,
            key="nav_selectbox",
            label_visibility="collapsed"
        )

    with logout_col:
        if st.button("🚪 Logout", key="logout_btn", use_container_width=True):
            _do_logout()

    # ── Handle navigation change ──────────────────────────────────
    selected_module = label_to_module.get(selected_label)
    if selected_module != active:
        _set_module(selected_module)

    st.divider()

    # ── Admin submenu ─────────────────────────────────────────────
    admin_items = [
        ("📄 Statements",     "Statements"),
        ("👤 Users",          "Users"),
        ("➕ Create User",    "Create User"),
        ("🏪 Stockists",      "Stockists"),
        ("📦 Products",       "Products"),
        ("📍 Territories",    "Territories"),
        ("🔐 Reset Password", "Reset User Password"),
        ("📜 Audit Logs",     "Audit Logs"),
        ("🔒 Lock/Unlock",    "Lock / Unlock Statements"),
        ("📈 Analytics",      "Analytics"),
    ]

    if role == "admin" and active == "ADMIN":
        admin_section_labels = ["— Select Section —"] + [label for label, _ in admin_items]
        admin_section_map = {label: key for label, key in admin_items}

        current_section = st.session_state.get("admin_section")
        current_section_label = next(
            (lbl for lbl, key in admin_items if key == current_section),
            "— Select Section —"
        )
        current_section_index = admin_section_labels.index(current_section_label)

        selected_section_label = st.selectbox(
            "Admin Section",
            admin_section_labels,
            index=current_section_index,
            key="admin_section_selectbox"
        )

        if selected_section_label == "— Select Section —":
            new_section = None
        else:
            new_section = admin_section_map.get(selected_section_label)

        if new_section != current_section:
            st.session_state.admin_section = new_section
            st.rerun()

        st.divider()

    # ── Route to module ───────────────────────────────────────────
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
    if name not in ("STATEMENT", "ADMIN"):
        for k in ["statement_id", "product_index", "statement_year",
                  "statement_month", "selected_stockist_id", "engine_stage"]:
            st.session_state[k] = None
    if name != "ADMIN":
        st.session_state.admin_section = None
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
    Use the **Navigate** dropdown above to go to any module.

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
