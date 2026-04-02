import streamlit as st
from datetime import datetime, date, timedelta
from anchors.supabase_client import admin_supabase, safe_exec


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
        nav_options.append("🔔 Notifications")
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
        "🔔 Notifications": "NOTIFICATIONS",
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
        admin_section_labels = [label for label, _ in admin_items]
        admin_section_map = {label: key for label, key in admin_items}

        current_section = st.session_state.get("admin_section")
        current_section_label = next(
            (lbl for lbl, key in admin_items if key == current_section),
            admin_section_labels[0]
        )
        current_section_index = admin_section_labels.index(current_section_label)

        selected_section_label = st.selectbox(
            "Admin Section",
            admin_section_labels,
            index=current_section_index,
            key="admin_section_selectbox"
        )
        new_section = admin_section_map[selected_section_label]
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

    elif active == "NOTIFICATIONS":
        from modules.statement.notifications import run_notifications
        run_notifications()

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
    """Live dashboard — 7-section personal dashboard + AI assistant."""
    user = st.session_state.get("auth_user")
    if not user:
        st.error("Not logged in.")
        return

    # ── AI Business Assistant ─────────────────────────────────────
    try:
        from modules.ai.ai_assistant import run_ai_assistant
        run_ai_assistant()
    except Exception as _ai_err:
        st.caption(f"AI assistant unavailable: {_ai_err}")

    st.divider()

    # ── Live Dashboard ────────────────────────────────────────────
    if role == "admin":
        _dash_admin(user.id)
    else:
        _dash_render(user.id)


# ══════════════════════════════════════════════════════════════
# HOME DASHBOARD — helper functions
# ══════════════════════════════════════════════════════════════
MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

def _dash_admin(admin_id):
    st.markdown("### 🏠 Dashboard")

    users = safe_exec(
        admin_supabase.table("users")
        .select("id, username")
        .eq("is_active", True)
        .order("username"),
        "Error loading users"
    ) or []

    if not users:
        st.warning("No active users found.")
        return

    user_map = {u["id"]: u["username"] for u in users}

    selected_id = st.selectbox(
        "👤 Select User",
        options=list(user_map.keys()),
        format_func=lambda x: user_map[x],
        key="dash_admin_user_select"
    )

    st.divider()
    _dash_render(selected_id)


# ──────────────────────────────────────────────────────────────────
# MAIN DASHBOARD RENDERER
# ──────────────────────────────────────────────────────────────────
def _dash_render(user_id):
    today = date.today()
    current_month = today.month
    current_year  = today.year

    # ── Fetch user's stockists and territories once ───────────────
    us_rows = safe_exec(
        admin_supabase.table("user_stockists")
        .select("stockist_id, stockists(id, name)")
        .eq("user_id", user_id),
        "Error loading stockists"
    ) or []

    stockist_map = {}   # id → name
    for r in us_rows:
        s = r.get("stockists") or {}
        sid = s.get("id") or r.get("stockist_id")
        if sid:
            stockist_map[sid] = s.get("name", "Unknown")

    stockist_ids = list(stockist_map.keys())

    ut_rows = safe_exec(
        admin_supabase.table("user_territories")
        .select("territory_id")
        .eq("user_id", user_id),
        "Error loading territories"
    ) or []
    territory_ids = [r["territory_id"] for r in ut_rows if r.get("territory_id")]

    # ═══════════════════════════════════════════════════════════════
    # SECTION 1 — Red Flags
    # ═══════════════════════════════════════════════════════════════
    with st.expander("🚨 Red Flags — High Closing Stock", expanded=True):
        _dash_red_flags(stockist_ids, stockist_map)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 2 — Last DCR Date
    # ═══════════════════════════════════════════════════════════════
    with st.expander("📅 Last DCR Submission", expanded=True):
        _dash_last_dcr(user_id)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 3 — Statement Status per Stockist
    # ═══════════════════════════════════════════════════════════════
    with st.expander("📋 Statement Submission Status", expanded=True):
        _dash_stmt_status(user_id, stockist_ids, stockist_map)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 4 — Current Month Sales Summary
    # ═══════════════════════════════════════════════════════════════
    with st.expander(f"💰 This Month's Sales — {MONTH_NAMES[current_month]} {current_year}", expanded=True):
        _dash_monthly_sales(stockist_ids, current_month, current_year)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 5 — Birthdays & Anniversaries
    # ═══════════════════════════════════════════════════════════════
    with st.expander("🎂 Doctor Birthdays & Anniversaries (±7 days)", expanded=True):
        _dash_birthdays(territory_ids, today)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 6 — Outstanding > 45 Days
    # ═══════════════════════════════════════════════════════════════
    with st.expander("⏰ Outstanding Payments", expanded=True):
        _dash_outstanding(stockist_ids, stockist_map, today)

    # ═══════════════════════════════════════════════════════════════
    # SECTION 7 — Drafts & Unfinished
    # ═══════════════════════════════════════════════════════════════
    with st.expander("📝 Drafts & Unfinished Work", expanded=True):
        _dash_drafts(user_id, stockist_ids, stockist_map)


# ──────────────────────────────────────────────────────────────────
# SECTION 1 — RED FLAGS
# ──────────────────────────────────────────────────────────────────
def _dash_red_flags(stockist_ids, stockist_map):
    if not stockist_ids:
        st.info("No stockists assigned.")
        return

    rows = safe_exec(
        admin_supabase.table("monthly_summary")
        .select("year, month, stockist_id, product_id, total_issue, total_closing, products(name)")
        .in_("stockist_id", stockist_ids),
        "Error loading monthly summary"
    ) or []

    if not rows:
        st.success("✅ No data yet — no red flags.")
        return

    # Get latest month per stockist+product
    latest = {}
    for r in rows:
        key = (r["stockist_id"], r["product_id"])
        existing = latest.get(key)
        if not existing or (r["year"], r["month"]) > (existing["year"], existing["month"]):
            latest[key] = r

    flags = []
    for r in latest.values():
        issue   = float(r.get("total_issue")   or 0)
        closing = float(r.get("total_closing") or 0)
        product = (r.get("products") or {}).get("name", "Unknown")
        stockist = stockist_map.get(r["stockist_id"], "Unknown")
        period   = f"{MONTH_NAMES[r['month']]} {r['year']}"

        if issue > 0 and closing >= 2 * issue:
            flags.append({
                "Stockist": stockist,
                "Product":  product,
                "Closing":  int(closing),
                "Issue":    int(issue),
                "Flag":     "⚠️ Overstock (closing ≥ 2× issue)",
                "Period":   period
            })
        elif issue == 0 and closing > 0:
            flags.append({
                "Stockist": stockist,
                "Product":  product,
                "Closing":  int(closing),
                "Issue":    0,
                "Flag":     "🔴 Not Moving (zero issue)",
                "Period":   period
            })

    if not flags:
        st.success("✅ No red flags. All products are moving well.")
        return

    st.warning(f"**{len(flags)} red flag(s) found**")
    for f in flags:
        st.markdown(
            f"<div style='background:#fff5f5;border-left:4px solid #c0392b;"
            f"padding:0.6rem 0.8rem;border-radius:6px;margin-bottom:6px;font-size:0.88rem;'>"
            f"{f['Flag']}<br>"
            f"<b>{f['Stockist']}</b> — {f['Product']}<br>"
            f"<span style='color:#5a7268;'>Closing: {f['Closing']} | "
            f"Issue: {f['Issue']} | {f['Period']}</span>"
            f"</div>",
            unsafe_allow_html=True
        )


# ──────────────────────────────────────────────────────────────────
# SECTION 2 — LAST DCR DATE
# ──────────────────────────────────────────────────────────────────
def _dash_last_dcr(user_id):
    rows = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("report_date, area_type")
        .eq("user_id", user_id)
        .eq("status", "submitted")
        .eq("is_deleted", False)
        .order("report_date", desc=True)
        .limit(1),
        "Error loading DCR"
    ) or []

    if not rows:
        st.info("No DCR submitted yet.")
        return

    r     = rows[0]
    rdate = r["report_date"]
    area  = r.get("area_type", "")

    try:
        d    = date.fromisoformat(rdate)
        days = (date.today() - d).days
        ago  = f"{days} day(s) ago" if days > 0 else "Today"
    except Exception:
        ago = ""

    color = "#d4edda" if days <= 1 else ("#fff3cd" if days <= 3 else "#fff5f5")
    border = "#1a6b5a" if days <= 1 else ("#e67e22" if days <= 3 else "#c0392b")

    st.markdown(
        f"<div style='background:{color};border-left:4px solid {border};"
        f"padding:0.7rem 1rem;border-radius:6px;font-size:0.9rem;'>"
        f"<b>Last DCR:</b> {rdate} &nbsp;|&nbsp; {area} &nbsp;|&nbsp; "
        f"<span style='color:#5a7268;'>{ago}</span>"
        f"</div>",
        unsafe_allow_html=True
    )


# ──────────────────────────────────────────────────────────────────
# SECTION 3 — STATEMENT STATUS
# ──────────────────────────────────────────────────────────────────
def _dash_stmt_status(user_id, stockist_ids, stockist_map):
    if not stockist_ids:
        st.info("No stockists assigned.")
        return

    stmts = safe_exec(
        admin_supabase.table("statements")
        .select("stockist_id, year, month, status, final_submitted_at")
        .eq("user_id", user_id)
        .eq("status", "final")
        .in_("stockist_id", stockist_ids)
        .order("year", desc=True)
        .order("month", desc=True),
        "Error loading statements"
    ) or []

    if not stmts:
        st.info("No final statements submitted yet.")
        return

    # Latest final per stockist
    latest = {}
    for s in stmts:
        sid = s["stockist_id"]
        if sid not in latest:
            latest[sid] = s

    for sid, s in latest.items():
        sname  = stockist_map.get(sid, "Unknown")
        month  = MONTH_NAMES.get(s["month"], str(s["month"]))
        year   = s["year"]
        sub_at = (s.get("final_submitted_at") or "")[:10]

        st.markdown(
            f"<div style='background:#f0faf7;border-left:4px solid #1a6b5a;"
            f"padding:0.6rem 0.9rem;border-radius:6px;margin-bottom:6px;font-size:0.88rem;'>"
            f"✅ <b>{sname}</b> — submitted for <b>{month} {year}</b>"
            f"<br><span style='color:#5a7268;font-size:0.78rem;'>Submitted on: {sub_at}</span>"
            f"</div>",
            unsafe_allow_html=True
        )


# ──────────────────────────────────────────────────────────────────
# SECTION 4 — MONTHLY SALES SUMMARY
# ──────────────────────────────────────────────────────────────────
def _dash_monthly_sales(stockist_ids, month, year):
    if not stockist_ids:
        st.info("No stockists assigned.")
        return

    month_start = f"{year}-{month:02d}-01"
    if month == 12:
        month_end = f"{year+1}-01-01"
    else:
        month_end = f"{year}-{month+1:02d}-01"

    # Gross Sale — invoices to user's stockists this month
    inv_rows = safe_exec(
        admin_supabase.table("ops_documents")
        .select("invoice_total")
        .eq("ops_type", "STOCK_OUT")
        .eq("stock_as", "normal")
        .eq("is_deleted", False)
        .in_("to_entity_id", stockist_ids)
        .gte("ops_date", month_start)
        .lt("ops_date", month_end),
        "Error loading invoices"
    ) or []
    gross_sale = sum(float(r.get("invoice_total") or 0) for r in inv_rows)

    # Credit Notes — to user's stockists this month
    cn_rows = safe_exec(
        admin_supabase.table("ops_documents")
        .select("id")
        .eq("stock_as", "credit_note")
        .eq("is_deleted", False)
        .in_("from_entity_id", stockist_ids)
        .gte("ops_date", month_start)
        .lt("ops_date", month_end),
        "Error loading credit notes"
    ) or []
    cn_ids = [r["id"] for r in cn_rows]
    cn_amount = 0.0
    if cn_ids:
        cn_lines = safe_exec(
            admin_supabase.table("ops_lines")
            .select("net_amount")
            .in_("ops_document_id", cn_ids),
            "Error loading CN lines"
        ) or []
        cn_amount = sum(float(r.get("net_amount") or 0) for r in cn_lines)

    # Payments — from user's stockists this month
    pay_rows = safe_exec(
        admin_supabase.table("ops_documents")
        .select("id")
        .eq("ops_type", "ADJUSTMENT")
        .eq("is_deleted", False)
        .in_("from_entity_id", stockist_ids)
        .gte("ops_date", month_start)
        .lt("ops_date", month_end),
        "Error loading payments"
    ) or []
    pay_ids = [r["id"] for r in pay_rows]
    payment_total = 0.0
    if pay_ids:
        pay_ledger = safe_exec(
            admin_supabase.table("financial_ledger")
            .select("credit")
            .in_("ops_document_id", pay_ids),
            "Error loading payment ledger"
        ) or []
        payment_total = sum(float(r.get("credit") or 0) for r in pay_ledger)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("💊 Gross Sale", f"₹{gross_sale:,.0f}")
    with col2:
        st.metric("💳 Payments Received", f"₹{payment_total:,.0f}")

    st.metric("📝 Credit Notes", f"₹{cn_amount:,.0f}")

    if gross_sale > 0:
        collection_pct = (payment_total / gross_sale) * 100
        color = "#d4edda" if collection_pct >= 80 else ("#fff3cd" if collection_pct >= 50 else "#fff5f5")
        st.markdown(
            f"<div style='background:{color};padding:0.5rem 0.8rem;"
            f"border-radius:6px;font-size:0.85rem;margin-top:8px;'>"
            f"Collection efficiency: <b>{collection_pct:.1f}%</b>"
            f"</div>",
            unsafe_allow_html=True
        )


# ──────────────────────────────────────────────────────────────────
# SECTION 5 — BIRTHDAYS & ANNIVERSARIES
# ──────────────────────────────────────────────────────────────────
def _dash_birthdays(territory_ids, today):
    if not territory_ids:
        st.info("No territories assigned.")
        return

    # Get doctor IDs in these territories
    dt_rows = safe_exec(
        admin_supabase.table("doctor_territories")
        .select("doctor_id")
        .in_("territory_id", territory_ids),
        "Error loading doctor territories"
    ) or []
    doctor_ids = list({r["doctor_id"] for r in dt_rows})

    if not doctor_ids:
        st.info("No doctors found in your territories.")
        return

    # Supabase .in_() breaks with large lists — chunk into batches of 100
    doctors = []
    for i in range(0, len(doctor_ids), 100):
        batch = doctor_ids[i:i+100]
        chunk = safe_exec(
            admin_supabase.table("doctors")
            .select("id, name, date_of_birth, date_of_anniversary, specialization")
            .in_("id", batch)
            .eq("is_active", True),
            "Error loading doctors"
        ) or []
        doctors.extend(chunk)

    window_start = today - timedelta(days=7)
    window_end   = today + timedelta(days=7)

    events = []
    for doc in doctors:
        name = doc["name"]
        spec = doc.get("specialization") or ""

        for field, label, icon in [
            ("date_of_birth",        "Birthday",     "🎂"),
            ("date_of_anniversary",  "Anniversary",  "💍"),
        ]:
            raw = doc.get(field)
            if not raw:
                continue
            try:
                d = date.fromisoformat(raw)
                # Compare day+month only — use this year
                this_year = d.replace(year=today.year)
                # Also check last year in case it crossed Dec/Jan boundary
                for candidate in [this_year, d.replace(year=today.year - 1), d.replace(year=today.year + 1)]:
                    if window_start <= candidate <= window_end:
                        days_diff = (candidate - today).days
                        if days_diff == 0:
                            when = "Today! 🎉"
                        elif days_diff > 0:
                            when = f"in {days_diff} day(s)"
                        else:
                            when = f"{abs(days_diff)} day(s) ago"
                        events.append({
                            "icon": icon,
                            "label": label,
                            "name": name,
                            "spec": spec,
                            "date": candidate.strftime("%d %b"),
                            "when": when,
                            "sort": days_diff
                        })
                        break
            except Exception:
                continue

    if not events:
        st.info("No birthdays or anniversaries in the ±7 day window.")
        return

    events.sort(key=lambda x: x["sort"])

    upcoming = [e for e in events if e["sort"] >= 0]
    past     = [e for e in events if e["sort"] < 0]

    if upcoming:
        st.markdown("**Upcoming**")
        for e in upcoming:
            bg = "#fff8e1" if e["sort"] == 0 else "#f0faf7"
            st.markdown(
                f"<div style='background:{bg};border-left:4px solid #1a6b5a;"
                f"padding:0.55rem 0.8rem;border-radius:6px;margin-bottom:5px;font-size:0.87rem;'>"
                f"{e['icon']} <b>{e['name']}</b>"
                f"{'  <span style="color:#5a7268;font-size:0.78rem;">(' + e['spec'] + ')</span>' if e['spec'] else ''}"
                f"<br><span style='color:#5a7268;'>{e['label']} — {e['date']} &nbsp;·&nbsp; {e['when']}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

    if past:
        st.markdown("**Recent (past 7 days)**")
        for e in past:
            st.markdown(
                f"<div style='background:#f9f9f9;border-left:4px solid #9ab4ad;"
                f"padding:0.55rem 0.8rem;border-radius:6px;margin-bottom:5px;font-size:0.87rem;'>"
                f"{e['icon']} <b>{e['name']}</b>"
                f"{'  <span style="color:#5a7268;font-size:0.78rem;">(' + e['spec'] + ')</span>' if e['spec'] else ''}"
                f"<br><span style='color:#5a7268;'>{e['label']} — {e['date']} &nbsp;·&nbsp; {e['when']}</span>"
                f"</div>",
                unsafe_allow_html=True
            )


# ──────────────────────────────────────────────────────────────────
# SECTION 6 — OUTSTANDING > 45 DAYS
# ──────────────────────────────────────────────────────────────────
def _dash_outstanding(stockist_ids, stockist_map, today):
    if not stockist_ids:
        st.info("No stockists assigned.")
        return

    inv_rows = safe_exec(
        admin_supabase.table("ops_documents")
        .select("ops_no, ops_date, outstanding_balance, to_entity_id")
        .eq("ops_type", "STOCK_OUT")
        .eq("stock_as", "normal")
        .eq("is_deleted", False)
        .in_("to_entity_id", stockist_ids)
        .gt("outstanding_balance", 0),
        "Error loading outstanding"
    ) or []

    if not inv_rows:
        st.success("✅ No outstanding invoices.")
        return

    total_outstanding = 0.0
    total_over_45     = 0.0
    by_stockist       = {}

    for inv in inv_rows:
        bal = float(inv.get("outstanding_balance") or 0)
        total_outstanding += bal
        try:
            inv_date = date.fromisoformat(inv["ops_date"])
            days_old = (today - inv_date).days
        except Exception:
            days_old = 0

        sid   = inv["to_entity_id"]
        sname = stockist_map.get(sid, "Unknown")
        by_stockist.setdefault(sname, {"total": 0.0, "over45": 0.0, "invoices": []})
        by_stockist[sname]["total"] += bal
        by_stockist[sname]["invoices"].append({
            "ops_no":   inv["ops_no"],
            "date":     inv["ops_date"],
            "bal":      bal,
            "days_old": days_old,
            "over45":   days_old > 45
        })
        if days_old > 45:
            total_over_45 += bal
            by_stockist[sname]["over45"] += bal

    # Summary metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📊 Total Outstanding", f"₹{total_outstanding:,.0f}")
    with col2:
        st.metric("⚠️ Outstanding > 45 Days", f"₹{total_over_45:,.0f}")

    st.divider()

    # Per stockist breakdown
    for sname, data in sorted(by_stockist.items(), key=lambda x: -x[1]["over45"]):
        has_old = data["over45"] > 0
        header_color = "#fff5f5" if has_old else "#f0faf7"
        border_color = "#c0392b" if has_old else "#1a6b5a"

        st.markdown(
            f"<div style='background:{header_color};border-left:4px solid {border_color};"
            f"padding:0.55rem 0.8rem;border-radius:6px;margin-bottom:4px;font-size:0.88rem;'>"
            f"<b>{sname}</b> &nbsp;|&nbsp; Total: ₹{data['total']:,.0f}"
            + (f" &nbsp;|&nbsp; <span style='color:#c0392b;'>Over 45d: ₹{data['over45']:,.0f}</span>" if has_old else "")
            + "</div>",
            unsafe_allow_html=True
        )
        for inv in sorted(data["invoices"], key=lambda x: -x["days_old"]):
            flag = " 🔴" if inv["over45"] else ""
            st.markdown(
                f"<div style='padding:0.3rem 0.8rem 0.3rem 1.5rem;"
                f"font-size:0.8rem;color:#5a7268;'>"
                f"{inv['ops_no']} &nbsp;·&nbsp; {inv['date']} "
                f"&nbsp;·&nbsp; ₹{inv['bal']:,.0f} "
                f"&nbsp;·&nbsp; {inv['days_old']}d{flag}"
                f"</div>",
                unsafe_allow_html=True
            )


# ──────────────────────────────────────────────────────────────────
# SECTION 7 — DRAFTS & UNFINISHED
# ──────────────────────────────────────────────────────────────────
def _dash_drafts(user_id, stockist_ids, stockist_map):
    found_any = False

    # DCR drafts
    dcr_drafts = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("report_date, area_type, current_step")
        .eq("user_id", user_id)
        .eq("status", "draft")
        .eq("is_deleted", False)
        .order("report_date", desc=True),
        "Error loading DCR drafts"
    ) or []

    if dcr_drafts:
        found_any = True
        st.markdown("**📞 Unfinished DCR(s)**")
        for r in dcr_drafts:
            step = r.get("current_step") or 1
            st.markdown(
                f"<div style='background:#fff8e1;border-left:4px solid #e67e22;"
                f"padding:0.55rem 0.8rem;border-radius:6px;margin-bottom:5px;font-size:0.87rem;'>"
                f"⏳ <b>{r['report_date']}</b> &nbsp;|&nbsp; {r.get('area_type','')} "
                f"&nbsp;|&nbsp; <span style='color:#5a7268;'>Stopped at Step {step}/4</span>"
                f"</div>",
                unsafe_allow_html=True
            )

    # Statement drafts (non-final, non-locked)
    if stockist_ids:
        stmt_drafts = safe_exec(
            admin_supabase.table("statements")
            .select("stockist_id, year, month, status, engine_stage, last_saved_at")
            .eq("user_id", user_id)
            .in_("stockist_id", stockist_ids)
            .neq("status", "final"),
            "Error loading statement drafts"
        ) or []

        stmt_drafts = [s for s in stmt_drafts if s.get("status") not in (None, "")]

        if stmt_drafts:
            found_any = True
            st.markdown("**📦 Unfinished Statement(s)**")
            for s in stmt_drafts:
                sname   = stockist_map.get(s["stockist_id"], "Unknown")
                month   = MONTH_NAMES.get(s["month"], str(s["month"]))
                year    = s["year"]
                stage   = s.get("engine_stage") or s.get("status") or "In Progress"
                saved   = (s.get("last_saved_at") or "")[:10]
                st.markdown(
                    f"<div style='background:#fff8e1;border-left:4px solid #e67e22;"
                    f"padding:0.55rem 0.8rem;border-radius:6px;margin-bottom:5px;font-size:0.87rem;'>"
                    f"⏳ <b>{sname}</b> — {month} {year}"
                    f"<br><span style='color:#5a7268;font-size:0.8rem;'>Stage: {stage}"
                    + (f" &nbsp;·&nbsp; Last saved: {saved}" if saved else "")
                    + "</span></div>",
                    unsafe_allow_html=True
                )

    if not found_any:
        st.success("✅ No drafts or unfinished work. All caught up!")
