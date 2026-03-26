import streamlit as st
from datetime import datetime, date, timedelta


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
    from datetime import datetime, date, timedelta
    from anchors.supabase_client import admin_supabase, safe_exec

    st.title("🏠 Ivy Pharmaceuticals")

    # ── Admin: pick which user to view ───────────────────────────
    if role == "admin":
        users_list = safe_exec(
            admin_supabase.table("users")
            .select("id, username")
            .eq("is_active", True)
            .order("username"), ""
        ) or []
        user_map = {u["id"]: u["username"] for u in users_list}
        if not user_map:
            st.warning("No active users found.")
            return
        stored = st.session_state.get("dashboard_user_id") or list(user_map.keys())[0]
        sel_uid = st.selectbox(
            "👤 View dashboard for user:",
            options=list(user_map.keys()),
            format_func=lambda x: user_map.get(x, x),
            index=list(user_map.keys()).index(stored) if stored in user_map else 0,
            key="dashboard_user_select"
        )
        st.session_state.dashboard_user_id = sel_uid
        view_user_id = sel_uid
        view_username = user_map.get(sel_uid, username)
        st.markdown(f"**Showing dashboard for: {view_username}**")
        st.divider()
    else:
        auth_user = st.session_state.get("auth_user")
        view_user_id = auth_user.id if auth_user else None
        view_username = username
        st.markdown(f"**Welcome, {username}!**")
        st.divider()

    if not view_user_id:
        st.error("Cannot identify user.")
        return

    today = date.today()

    # ── Fetch user's stockists ────────────────────────────────────
    us_rows = safe_exec(
        admin_supabase.table("user_stockists")
        .select("stockist_id, stockists(id, name)")
        .eq("user_id", view_user_id), ""
    ) or []
    stockist_map = {}
    for r in us_rows:
        s = r.get("stockists") or {}
        sid = s.get("id") or r.get("stockist_id")
        if sid:
            stockist_map[sid] = s.get("name", "Unknown")
    stockist_ids = list(stockist_map.keys())

    # ── Fetch user's territories ──────────────────────────────────
    ut_rows = safe_exec(
        admin_supabase.table("user_territories")
        .select("territory_id")
        .eq("user_id", view_user_id), ""
    ) or []
    territory_ids = [r["territory_id"] for r in ut_rows if r.get("territory_id")]

    # ==============================================================
    # SECTION 1 — RED FLAGS (from monthly_summary)
    # ==============================================================
    st.subheader("🚨 Red Flags — High Closing Stock")

    if not stockist_ids:
        st.info("No stockists linked to this user.")
    else:
        summary_rows = safe_exec(
            admin_supabase.table("monthly_summary")
            .select("year, month, stockist_id, total_issue, total_closing, products(name)")
            .in_("stockist_id", stockist_ids)
            .order("year", desc=True)
            .order("month", desc=True), ""
        ) or []

        # Keep only the latest month per stockist+product
        seen = {}
        for r in summary_rows:
            key = (r["stockist_id"], r.get("products", {}).get("name", ""))
            if key not in seen:
                seen[key] = r

        flags = []
        for (sid, pname), r in seen.items():
            issue   = float(r.get("total_issue")   or 0)
            closing = float(r.get("total_closing")  or 0)
            sname   = stockist_map.get(sid, "Unknown")
            ym      = f"{r['year']}-{r['month']:02d}"
            if issue > 0 and closing >= 2 * issue:
                flags.append({"Stockist": sname, "Product": pname,
                               "Closing": int(closing), "Issue": int(issue),
                               "Flag": "⚠️ Overstock (closing ≥ 2× issue)", "Month": ym})
            elif issue == 0 and closing > 0:
                flags.append({"Stockist": sname, "Product": pname,
                               "Closing": int(closing), "Issue": 0,
                               "Flag": "🛑 Not moving (zero issue)", "Month": ym})

        if flags:
            import pandas as pd
            df_flags = pd.DataFrame(flags).sort_values(["Stockist", "Product"])
            st.dataframe(df_flags, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No red flags — all products within normal range.")

    st.divider()

    # ==============================================================
    # SECTION 2 — LAST DCR DATE
    # ==============================================================
    st.subheader("📅 Last DCR Update")

    last_dcr = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("report_date")
        .eq("user_id", view_user_id)
        .eq("status", "submitted")
        .eq("is_deleted", False)
        .order("report_date", desc=True)
        .limit(1), ""
    )
    if last_dcr:
        last_date = last_dcr[0]["report_date"]
        days_ago = (today - date.fromisoformat(last_date)).days
        if days_ago == 0:
            st.success(f"✅ DCR submitted today — {last_date}")
        elif days_ago == 1:
            st.success(f"✅ Last DCR: {last_date} (yesterday)")
        elif days_ago <= 3:
            st.info(f"📅 Last DCR: {last_date} ({days_ago} days ago)")
        else:
            st.warning(f"⚠️ Last DCR: {last_date} ({days_ago} days ago) — please update")
    else:
        st.warning("⚠️ No DCR submitted yet.")

    st.divider()

    # ==============================================================
    # SECTION 3 — STATEMENT SUBMISSION STATUS
    # ==============================================================
    st.subheader("📋 Statement Submission Status")

    if not stockist_ids:
        st.info("No stockists linked.")
    else:
        # Get latest final statement per stockist
        stmts = safe_exec(
            admin_supabase.table("statements")
            .select("stockist_id, year, month, status")
            .in_("stockist_id", stockist_ids)
            .eq("status", "final")
            .order("year", desc=True)
            .order("month", desc=True), ""
        ) or []

        # Keep latest per stockist
        latest_stmt = {}
        for s in stmts:
            sid = s["stockist_id"]
            if sid not in latest_stmt:
                latest_stmt[sid] = s

        # Also check drafts
        draft_stmts = safe_exec(
            admin_supabase.table("statements")
            .select("stockist_id, year, month, status, engine_stage")
            .in_("stockist_id", stockist_ids)
            .neq("status", "final")
            .order("updated_at", desc=True), ""
        ) or []
        draft_map = {}
        for s in draft_stmts:
            sid = s["stockist_id"]
            if sid not in draft_map:
                draft_map[sid] = s

        import calendar
        for sid, sname in sorted(stockist_map.items(), key=lambda x: x[1]):
            if sid in latest_stmt:
                s = latest_stmt[sid]
                month_name = calendar.month_name[s["month"]]
                st.write(f"✅ **{sname}** — submitted for **{month_name} {s['year']}**")
            elif sid in draft_map:
                s = draft_map[sid]
                month_name = calendar.month_name[s["month"]]
                stage = s.get("engine_stage") or s.get("status") or "in progress"
                st.write(f"🟡 **{sname}** — {month_name} {s['year']} draft ({stage})")
            else:
                st.write(f"⚠️ **{sname}** — not yet submitted")

    st.divider()

    # ==============================================================
    # SECTION 4 — CURRENT MONTH SALES SUMMARY
    # ==============================================================
    st.subheader(f"💰 Sales Summary — {today.strftime('%B %Y')}")

    if not stockist_ids:
        st.info("No stockists linked.")
    else:
        month_start = today.replace(day=1).isoformat()
        month_end   = today.isoformat()

        # Gross Sale — invoices to user's stockists this month
        invoices = safe_exec(
            admin_supabase.table("ops_documents")
            .select("invoice_total")
            .eq("ops_type", "STOCK_OUT")
            .eq("stock_as", "normal")
            .eq("is_deleted", False)
            .eq("to_entity_type", "Stockist")
            .in_("to_entity_id", stockist_ids)
            .gte("ops_date", month_start)
            .lte("ops_date", month_end), ""
        ) or []
        gross_sale = sum(float(r.get("invoice_total") or 0) for r in invoices)

        # Payments — credits in financial_ledger for user's stockists this month
        pay_docs = safe_exec(
            admin_supabase.table("ops_documents")
            .select("id")
            .eq("ops_type", "ADJUSTMENT")
            .eq("is_deleted", False)
            .in_("from_entity_id", stockist_ids)
            .gte("ops_date", month_start)
            .lte("ops_date", month_end), ""
        ) or []
        pay_ids = [r["id"] for r in pay_docs]
        total_payments = 0.0
        if pay_ids:
            pay_ledger = safe_exec(
                admin_supabase.table("financial_ledger")
                .select("credit")
                .in_("ops_document_id", pay_ids), ""
            ) or []
            total_payments = sum(float(r.get("credit") or 0) for r in pay_ledger)

        # Credit Notes — for user's stockists this month
        cn_docs = safe_exec(
            admin_supabase.table("ops_documents")
            .select("id")
            .eq("stock_as", "credit_note")
            .eq("is_deleted", False)
            .in_("to_entity_id", stockist_ids)
            .gte("ops_date", month_start)
            .lte("ops_date", month_end), ""
        ) or []
        cn_ids = [r["id"] for r in cn_docs]
        total_cn = 0.0
        if cn_ids:
            cn_lines = safe_exec(
                admin_supabase.table("ops_lines")
                .select("net_amount")
                .in_("ops_document_id", cn_ids), ""
            ) or []
            total_cn = sum(float(r.get("net_amount") or 0) for r in cn_lines)

        col1, col2, col3 = st.columns(3)
        col1.metric("🧾 Gross Sale",    f"₹{gross_sale:,.0f}")
        col2.metric("💳 Payments",      f"₹{total_payments:,.0f}")
        col3.metric("📝 Credit Notes",  f"₹{total_cn:,.0f}")

    st.divider()

    # ==============================================================
    # SECTION 5 — BIRTHDAYS & ANNIVERSARIES (±7 days)
    # ==============================================================
    st.subheader("🎂 Doctor Birthdays & Anniversaries (±7 days)")

    if not territory_ids:
        st.info("No territories linked.")
    else:
        # Get doctor IDs in user's territories
        dt_rows = safe_exec(
            admin_supabase.table("doctor_territories")
            .select("doctor_id")
            .in_("territory_id", territory_ids), ""
        ) or []
        doc_ids = list({r["doctor_id"] for r in dt_rows if r.get("doctor_id")})

        celebrations = []
        if doc_ids:
            doctors = safe_exec(
                admin_supabase.table("doctors")
                .select("name, date_of_birth, date_of_anniversary")
                .in_("id", doc_ids)
                .eq("is_active", True), ""
            ) or []

            for doc in doctors:
                name = doc["name"]
                for field, label, emoji in [
                    ("date_of_birth",        "Birthday",     "🎂"),
                    ("date_of_anniversary",  "Anniversary",  "💍"),
                ]:
                    raw = doc.get(field)
                    if not raw:
                        continue
                    try:
                        d = date.fromisoformat(raw)
                        # Compare day+month only against today ±7
                        this_year = d.replace(year=today.year)
                        diff = (this_year - today).days
                        # Handle year boundary (e.g., Dec 28 when today is Jan 2)
                        if diff > 180:
                            diff -= 365
                        elif diff < -180:
                            diff += 365
                        if -7 <= diff <= 7:
                            if diff < 0:
                                timing = f"{abs(diff)} day(s) ago"
                            elif diff == 0:
                                timing = "TODAY 🎉"
                            else:
                                timing = f"in {diff} day(s)"
                            celebrations.append({
                                "Doctor": name,
                                "Event":  f"{emoji} {label}",
                                "Date":   this_year.strftime("%d %b"),
                                "When":   timing,
                                "_diff":  diff
                            })
                    except Exception:
                        continue

        if celebrations:
            celebrations.sort(key=lambda x: x["_diff"])
            # Upcoming
            upcoming = [c for c in celebrations if c["_diff"] >= 0]
            recent   = [c for c in celebrations if c["_diff"] < 0]
            if upcoming:
                st.write("**📅 Upcoming:**")
                for c in upcoming:
                    st.write(f"{c['Event']} **{c['Doctor']}** — {c['Date']} ({c['When']})")
            if recent:
                st.write("**🕐 Recent:**")
                for c in recent:
                    st.write(f"{c['Event']} **{c['Doctor']}** — {c['Date']} ({c['When']})")
        else:
            st.info("No birthdays or anniversaries in the next/last 7 days.")

    st.divider()

    # ==============================================================
    # SECTION 6 — OUTSTANDING (from financial_ledger)
    # ==============================================================
    st.subheader("⏰ Party Outstanding")

    if not stockist_ids:
        st.info("No stockists linked.")
    else:
        # Get all ledger entries for user's stockists
        ledger = safe_exec(
            admin_supabase.table("financial_ledger")
            .select("party_id, debit, credit")
            .in_("party_id", stockist_ids), ""
        ) or []

        # Calculate balance per stockist
        balances = {}
        for row in ledger:
            pid = row["party_id"]
            if pid not in balances:
                balances[pid] = 0.0
            balances[pid] += float(row.get("debit") or 0) - float(row.get("credit") or 0)

        # Get oldest unpaid invoice date per stockist for 45-day check
        unpaid_invoices = safe_exec(
            admin_supabase.table("ops_documents")
            .select("to_entity_id, ops_date, outstanding_balance")
            .eq("ops_type", "STOCK_OUT")
            .eq("stock_as", "normal")
            .eq("is_deleted", False)
            .in_("to_entity_id", stockist_ids)
            .gt("outstanding_balance", 0), ""
        ) or []

        # Oldest invoice date per stockist
        oldest_inv = {}
        for inv in unpaid_invoices:
            sid = inv["to_entity_id"]
            d = inv.get("ops_date")
            if d:
                if sid not in oldest_inv or d < oldest_inv[sid]:
                    oldest_inv[sid] = d

        total_outstanding = 0.0
        total_above_45    = 0.0
        any_outstanding   = False

        for sid, sname in sorted(stockist_map.items(), key=lambda x: x[1]):
            bal = balances.get(sid, 0.0)
            if bal <= 0:
                continue
            any_outstanding = True
            total_outstanding += bal

            oldest = oldest_inv.get(sid)
            days_old = 0
            if oldest:
                days_old = (today - date.fromisoformat(oldest)).days

            if days_old > 45:
                total_above_45 += bal
                st.error(f"🔴 **{sname}** — ₹{bal:,.0f} outstanding "
                         f"(oldest invoice: {days_old} days)")
            elif bal > 0:
                st.warning(f"🟡 **{sname}** — ₹{bal:,.0f} outstanding "
                           f"(oldest invoice: {days_old} days)")

        if any_outstanding:
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("📊 Total Outstanding",    f"₹{total_outstanding:,.0f}")
            c2.metric("🔴 Outstanding > 45 Days", f"₹{total_above_45:,.0f}")
        else:
            st.success("✅ No outstanding balance for any stockist.")

    st.divider()

    # ==============================================================
    # SECTION 7 — DRAFTS & UNFINISHED WORK
    # ==============================================================
    st.subheader("📝 Drafts & Unfinished Work")

    any_draft = False

    # DCR drafts
    dcr_drafts = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("report_date, area_type, current_step")
        .eq("user_id", view_user_id)
        .eq("status", "draft")
        .eq("is_deleted", False)
        .order("report_date", desc=True), ""
    ) or []

    if dcr_drafts:
        any_draft = True
        for d in dcr_drafts:
            step = d.get("current_step") or 1
            st.warning(
                f"📞 **Unfinished DCR** — {d['report_date']} "
                f"({d['area_type']}) — stopped at Step {step}/4. "
                f"Go to DCR to complete."
            )

    # Statement drafts
    if stockist_ids:
        stmt_drafts = safe_exec(
            admin_supabase.table("statements")
            .select("stockist_id, year, month, status, engine_stage")
            .in_("stockist_id", stockist_ids)
            .neq("status", "final")
            .order("updated_at", desc=True), ""
        ) or []

        import calendar
        for s in stmt_drafts:
            any_draft = True
            sid     = s["stockist_id"]
            sname   = stockist_map.get(sid, "Unknown Stockist")
            mname   = calendar.month_name[s["month"]]
            stage   = s.get("engine_stage") or s.get("status") or "in progress"
            st.warning(
                f"📦 **Unfinished Statement** — {sname} | "
                f"{mname} {s['year']} | Stage: {stage}. "
                f"Go to Statement to complete."
            )

    if not any_draft:
        st.success("✅ No pending drafts or unfinished work.")
