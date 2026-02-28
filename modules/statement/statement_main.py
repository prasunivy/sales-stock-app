"""
Statement Main Module
Contains: run_statement(), run_reports(), run_admin_panel()
Extracted from the original monolithic app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from anchors.supabase_client import supabase, admin_supabase, safe_exec


# ======================================================
# CACHED DATA LOADERS
# ======================================================

@st.cache_data(ttl=3600)
def load_products_cached():
    return supabase.table("products") \
        .select("*") \
        .order("name") \
        .execute().data


@st.cache_data(ttl=3600)
def load_users_cached():
    return supabase.table("users") \
        .select("id, username, role, is_active") \
        .order("username") \
        .execute().data


@st.cache_data(ttl=3600)
def load_stockists_cached():
    return supabase.table("stockists") \
        .select("id, name") \
        .order("name") \
        .execute().data


@st.cache_data(ttl=300)
def load_monthly_summary_cached(stockist_ids):
    if not stockist_ids:
        return []
    return admin_supabase.table("monthly_summary") \
        .select("""
            year,
            month,
            total_issue,
            total_closing,
            total_order,
            products(name),
            stockist_id
        """) \
        .in_("stockist_id", stockist_ids) \
        .execute().data


# ======================================================
# HELPERS
# ======================================================

def get_previous_period(year, month):
    if year is None or month is None:
        return None, None
    if month == 1:
        return year - 1, 12
    return year, month - 1


def fetch_last_month_data(stockist_id, product_id, year, month):
    py, pm = get_previous_period(year, month)
    if py is None or pm is None:
        return 0.0, 0.0

    stmt = safe_exec(
        admin_supabase.table("statements")
        .select("id")
        .eq("stockist_id", stockist_id)
        .eq("year", py)
        .eq("month", pm)
        .eq("status", "final")
        .limit(1)
    )
    if not stmt:
        return 0.0, 0.0

    row = safe_exec(
        admin_supabase.table("statement_products")
        .select("closing,issue")
        .eq("statement_id", stmt[0]["id"])
        .eq("product_id", product_id)
        .limit(1)
    )
    if not row:
        return 0.0, 0.0
    return float(row[0]["closing"]), float(row[0]["issue"])


def fetch_last_month_closing_only(stockist_id, product_id, year, month):
    py, pm = get_previous_period(year, month)
    stmt = safe_exec(
        admin_supabase.table("statements")
        .select("id")
        .eq("stockist_id", stockist_id)
        .eq("year", py)
        .eq("month", pm)
        .eq("status", "final")
        .limit(1)
    )
    if not stmt:
        return 0
    row = safe_exec(
        admin_supabase.table("statement_products")
        .select("closing")
        .eq("statement_id", stmt[0]["id"])
        .eq("product_id", product_id)
        .limit(1)
    )
    return float(row[0]["closing"]) if row else 0


def fetch_statement_product(statement_id, product_id):
    rows = safe_exec(
        admin_supabase.table("statement_products")
        .select(
            "opening,purchase,issue,closing,calculated_closing,"
            "difference,order_qty,issue_guidance,stock_guidance"
        )
        .eq("statement_id", statement_id)
        .eq("product_id", product_id)
        .limit(1)
    )
    return rows[0] if rows else {}


def detect_red_flags(rows):
    overstock, zero_issue, mismatch = [], [], []
    for r in rows:
        issue = r.get("issue", 0) or 0
        closing = r.get("closing", 0) or 0
        diff = r.get("difference", 0) or 0
        product = r["products"]["name"]
        if issue > 0 and closing >= 2 * issue:
            overstock.append(product)
        if issue == 0 and closing > 0:
            zero_issue.append(product)
        if diff != 0:
            mismatch.append(product)
    return {"overstock": overstock, "zero_issue": zero_issue, "mismatch": mismatch}


def log_audit(*, action, message, performed_by, target_type=None, target_id=None, metadata=None):
    username = None
    try:
        u = supabase.table("users").select("username").eq("id", performed_by).limit(1).execute().data
        if u:
            username = u[0]["username"]
    except Exception:
        pass
    enriched = metadata or {}
    enriched["performed_by_username"] = username
    supabase.table("audit_logs").insert({
        "action": action,
        "message": message,
        "performed_by": performed_by,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": enriched
    }).execute()


# ======================================================
# STATEMENT SIDEBAR (user-facing)
# ======================================================

def _render_user_statement_sidebar(user_id):
    """Render the statement selection sidebar for regular users.
    Exact logic from original app.py."""

    st.divider()
    st.subheader("🗂 My Statements")

    # Stockist filter dropdown
    stockist_rows = safe_exec(
        admin_supabase.table("statements")
        .select("stockist_id, stockists(name)")
        .eq("user_id", user_id)
    )
    stockist_options = {
        r["stockist_id"]: r["stockists"]["name"]
        for r in stockist_rows
    }

    selected_stockist_filter = st.selectbox(
        "Select Stockist",
        options=[None] + list(stockist_options.keys()),
        format_func=lambda x: "— All Stockists —" if x is None else stockist_options[x]
    )

    my_statements = admin_supabase.table("statements") \
        .select("id, year, month, status, locked, current_product_index, stockist_id, stockists(name)") \
        .eq("user_id", user_id) \
        .order("year", desc=True) \
        .order("month", desc=True) \
        .execute().data

    if not my_statements:
        st.info("No statements yet")
    else:
        total_products = len(load_products_cached())

        for s in my_statements:
            # Filter by selected stockist
            if selected_stockist_filter and s["stockist_id"] != selected_stockist_filter:
                continue

            if s["locked"]:
                status = "🔒 Locked"
                action = "view"
            elif s["status"] == "final":
                status = "✅ Submitted"
                action = "view"
            else:
                progress = s.get("current_product_index") or 0
                status = f"📝 Draft ({progress}/{total_products})"
                action = "edit"

            label = f"{s['month']:02d}/{s['year']} — {status}"

            if st.button(f"👁 View • {label}", key=f"user_stmt_{s['id']}"):
                st.session_state.statement_id = s["id"]
                st.session_state.product_index = s.get("current_product_index") or 0
                st.session_state.statement_year = s["year"]
                st.session_state.statement_month = s["month"]
                st.session_state.selected_stockist_id = s["stockist_id"]
                st.session_state.engine_stage = action
                st.rerun()

    # Create / Resume new statement
    st.divider()
    st.subheader("➕ New Statement")

    stockists = safe_exec(
        supabase.table("user_stockists")
        .select("stockist_id, stockists(name)")
        .eq("user_id", user_id)
    )

    if not stockists:
        st.error(
            "❌ No stockists assigned to your user.\n\n"
            "Please contact admin to assign stockists."
        )
        st.stop()

    selected = st.selectbox(
        "Stockist", stockists,
        format_func=lambda x: x["stockists"]["name"]
    )

    today = date.today()
    year = st.selectbox("Year", [today.year - 1, today.year])
    month = st.selectbox(
        "Month",
        list(range(1, today.month + 1)) if year == today.year else list(range(1, 13))
    )

    if st.button("➕ Create / Resume"):
        res = admin_supabase.table("statements").upsert(
            {
                "user_id": user_id,
                "stockist_id": selected["stockist_id"],
                "year": year,
                "month": month,
                "status": "draft",
                "current_product_index": 0,
                "updated_at": datetime.utcnow().isoformat()
            },
            on_conflict="stockist_id,year,month",
            returning="representation"
        ).execute()

        stmt = res.data[0]

        if stmt["locked"]:
            st.error("Statement is locked by admin")
            st.stop()

        if stmt["status"] == "admin_edit":
            st.error("Statement is under admin correction")
            st.stop()

        if stmt.get("editing_by") and stmt["editing_by"] != user_id:
            st.error("Statement is open on another device")
            st.stop()

        # Acquire edit lock
        safe_exec(
            admin_supabase.table("statements")
            .update({
                "editing_by": user_id,
                "editing_at": datetime.utcnow().isoformat(),
                "last_saved_at": datetime.utcnow().isoformat()
            })
            .eq("id", stmt["id"])
        )

        st.session_state.statement_id = stmt["id"]
        st.session_state.product_index = stmt.get("current_product_index") or 0
        st.session_state.statement_year = stmt["year"]
        st.session_state.statement_month = stmt["month"]
        st.session_state.selected_stockist_id = stmt["stockist_id"]
        st.session_state.engine_stage = "edit"
        st.rerun()


# ======================================================
# MAIN ENTRY — run_statement()
# ======================================================

def run_statement():
    """Entry point called from core_router for the Statement module."""
    user_id = st.session_state.auth_user.id
    role = st.session_state.get("role", "user")

    # Render user sidebar
    if role == "user":
        _render_user_statement_sidebar(user_id)

    # ── Landing page (no statement loaded) ────────────────────────
    if (
        not st.session_state.get("statement_id")
        and st.session_state.get("engine_stage") not in ["edit", "preview", "view"]
    ):
        st.title("📦 Sales & Stock Statement")
        st.info("ℹ️ Use the selectors below to create or resume a statement. Drafts are saved automatically.")
        return

    sid = st.session_state.get("statement_id")
    stage = st.session_state.get("engine_stage")

    # Safety checks
    required_keys = ["statement_id", "statement_year", "statement_month", "selected_stockist_id"]
    if stage == "edit" and not all(st.session_state.get(k) is not None for k in required_keys):
        st.error("❌ Statement context incomplete. Please restart from sidebar.")
        return

    # ── PRODUCT EDIT ENGINE ────────────────────────────────────────
    if sid and stage == "edit":
        _run_product_engine(sid, user_id, role)
        return

    # ── PREVIEW / VIEW ─────────────────────────────────────────────
    if sid and stage in ("preview", "view"):
        _run_preview(sid, user_id, role)
        return


# ======================================================
# PRODUCT ENGINE (edit stage)
# ======================================================

def _run_product_engine(sid, user_id, role):
    idx = st.session_state.get("product_index", 0)
    products = load_products_cached()

    # Check statement is still editable
    stmt_meta = safe_exec(
        admin_supabase.table("statements")
        .select("status, locked, stockist_id, year, month, last_saved_at")
        .eq("id", sid)
        .limit(1)
    )
    if not stmt_meta:
        st.error("Statement not found")
        return
    stmt_meta = stmt_meta[0]

    # Reset option (draft only)
    if stmt_meta["status"] == "draft" and not stmt_meta["locked"]:
        with st.expander("🧹 Reset Statement (start over)", expanded=False):
            st.warning(
                "⚠️ This will permanently delete the current statement and all entered product data.\n\n"
                "You will be returned to the selection screen.\n\n**This action cannot be undone.**"
            )
            confirm_reset = st.checkbox("I understand and want to reset this statement")
            if st.button("🧹 Reset Statement Now", disabled=not confirm_reset, type="primary"):
                safe_exec(admin_supabase.table("statement_products").delete().eq("statement_id", sid))
                safe_exec(admin_supabase.table("statements").delete().eq("id", sid).eq("user_id", user_id))
                stockist_row = supabase.table("stockists").select("name") \
                    .eq("id", stmt_meta["stockist_id"]).limit(1).execute().data
                stockist_name = stockist_row[0]["name"] if stockist_row else "Unknown"
                log_audit(
                    action="reset_statement", target_type="statement", target_id=sid,
                    performed_by=user_id,
                    message=f"Statement reset for stockist {stockist_name} ({stmt_meta['month']:02d}/{stmt_meta['year']})",
                    metadata={"stockist_id": stmt_meta["stockist_id"], "year": stmt_meta["year"], "month": stmt_meta["month"]}
                )
                for k in ["statement_id", "product_index", "statement_year", "statement_month",
                           "selected_stockist_id", "engine_stage"]:
                    st.session_state.pop(k, None)
                st.success("✅ Statement reset successfully.")
                st.rerun()

    # Move to preview if done
    if idx >= len(products):
        st.session_state.engine_stage = "preview"
        st.rerun()

    product = products[idx]

    # Header
    st.subheader(f"Product {idx + 1} of {len(products)} — {product['name']}")
    if stmt_meta.get("last_saved_at"):
        st.caption(f"💾 Last saved at {stmt_meta['last_saved_at']}")
    else:
        st.caption("💾 Not saved yet")

    # Existing row
    row = safe_exec(
        admin_supabase.table("statement_products")
        .select("*")
        .eq("statement_id", sid)
        .eq("product_id", product["id"])
        .limit(1)
    )
    row = row[0] if row else {}

    # Last month data
    last_closing, last_issue = fetch_last_month_data(
        st.session_state.selected_stockist_id,
        product["id"],
        st.session_state.statement_year,
        st.session_state.statement_month
    )

    # Input fields
    opening = st.number_input("Opening", step=1, format="%d",
                               value=int(row.get("opening", last_closing)),
                               key=f"opening_{sid}_{product['id']}")
    st.caption(f"Last Month Issue: {last_issue}")
    purchase = st.number_input("Purchase", step=1, format="%d",
                                value=int(row.get("purchase", 0)),
                                key=f"purchase_{sid}_{product['id']}")
    issue = st.number_input("Issue", step=1, format="%d",
                             value=int(row.get("issue", 0)),
                             key=f"issue_{sid}_{product['id']}")
    calculated_closing = opening + purchase - issue
    closing = st.number_input("Closing", step=1, format="%d",
                               value=int(row.get("closing", calculated_closing)),
                               key=f"closing_{sid}_{product['id']}")

    diff = calculated_closing - closing
    if diff != 0:
        st.warning(f"Difference detected: {diff}")

    # Guidance
    live_row = fetch_statement_product(sid, product["id"])
    if live_row:
        st.divider()
        g1, g2, g3 = st.columns(3)
        with g1:
            st.metric("📦 Suggested Order", live_row.get("order_qty", 0))
        with g2:
            st.info(f"Issue Guidance: {live_row.get('issue_guidance', '—')}")
        with g3:
            st.warning(f"Stock Guidance: {live_row.get('stock_guidance', '—')}")
    else:
        st.info("Save the product to see guidance and order suggestion")

    # Navigation
    c1, c2 = st.columns(2)
    if c1.button("⬅ Previous", disabled=(idx == 0)):
        st.session_state.product_index -= 1
        st.rerun()

    if c2.button("💾 Save & Next"):
        safe_exec(
            admin_supabase.table("statement_products").upsert({
                "statement_id": sid,
                "product_id": product["id"],
                "opening": int(opening),
                "last_month_issue": int(last_issue),
                "purchase": int(purchase),
                "issue": int(issue),
                "closing": int(closing),
                "calculated_closing": calculated_closing,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="statement_id,product_id")
        )
        st.session_state.product_index += 1
        safe_exec(
            admin_supabase.table("statements")
            .update({"current_product_index": st.session_state.product_index,
                     "last_saved_at": datetime.utcnow().isoformat()})
            .eq("id", sid)
        )
        st.rerun()


# ======================================================
# PREVIEW / VIEW
# ======================================================

def _run_preview(sid, user_id, role):
    readonly = st.session_state.engine_stage == "view"

    rows = safe_exec(
        admin_supabase.table("statement_products")
        .select(
            "product_id,opening,purchase,issue,closing,difference,"
            "order_qty,issue_guidance,stock_guidance,"
            "products!statement_products_product_id_fkey(name)"
        )
        .eq("statement_id", sid)
    )

    df = pd.DataFrame([{
        "Product": r["products"]["name"],
        "Opening": r["opening"],
        "Purchase": r["purchase"],
        "Issue": r["issue"],
        "Closing": r["closing"],
        "Difference": r["difference"],
        "Order": r["order_qty"],
        "Issue Guidance": r["issue_guidance"],
        "Stock Guidance": r["stock_guidance"],
        "Product ID": r["product_id"]
    } for r in rows])

    if "Product ID" in df.columns:
        st.dataframe(df.drop(columns=["Product ID"]), use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

    # Timeline
    st.divider()
    st.subheader("🕒 Statement Timeline")
    timeline_logs = supabase.table("audit_logs") \
        .select("action, message, created_at, metadata") \
        .eq("target_type", "statement") \
        .eq("target_id", sid) \
        .order("created_at") \
        .execute().data

    if not timeline_logs:
        st.info("No activity recorded for this statement yet.")
    else:
        for log in timeline_logs:
            st.markdown(f"🕒 **{log['created_at']}** — {log.get('message') or log['action']}")
            if log.get("metadata"):
                with st.expander("Details", expanded=False):
                    st.json(log["metadata"])

    # Edit jump
    if not readonly and rows:
        st.subheader("✏️ Edit a Product")
        product_options = [(r["products"]["name"], r["product_id"]) for r in rows]
        selected = st.selectbox("Select product to edit", product_options, format_func=lambda x: x[0])
        if st.button("✏️ Edit Selected Product"):
            product_index_map = {
                p["id"]: idx
                for idx, p in enumerate(safe_exec(supabase.table("products").select("id").order("name")))
            }
            st.session_state.product_index = product_index_map[selected[1]]
            st.session_state.engine_stage = "edit"
            st.rerun()

    # Final submit (user)
    if role == "user" and not readonly:
        total_products = len(safe_exec(supabase.table("products").select("id")))
        entered_products = len(safe_exec(
            admin_supabase.table("statement_products").select("product_id").eq("statement_id", sid)
        ))
        if entered_products != total_products:
            st.error(f"Statement incomplete: {entered_products} of {total_products} products entered")
            return

        if st.button("✅ Final Submit Statement", type="primary"):
            safe_exec(
                admin_supabase.table("statements").update({
                    "status": "final",
                    "final_submitted_at": datetime.utcnow().isoformat(),
                    "editing_by": None,
                    "editing_at": None,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", sid)
            )
            stmt_row = supabase.table("statements").select("stockist_id, year, month") \
                .eq("id", sid).limit(1).execute().data
            stockist_name, stmt_month, stmt_year = "Unknown", None, None
            if stmt_row:
                stockist_id = stmt_row[0]["stockist_id"]
                stmt_month = stmt_row[0]["month"]
                stmt_year = stmt_row[0]["year"]
                s_row = supabase.table("stockists").select("name").eq("id", stockist_id).limit(1).execute().data
                if s_row:
                    stockist_name = s_row[0]["name"]
            log_audit(
                action="statement_submitted", target_type="statement", target_id=sid,
                performed_by=user_id,
                message=f"Statement submitted for stockist {stockist_name} ({stmt_month:02d}/{stmt_year})" if stmt_month else "Statement submitted",
                metadata={"stockist_name": stockist_name, "year": stmt_year, "month": stmt_month}
            )
            safe_exec(admin_supabase.rpc("populate_monthly_summary", {"p_statement_id": sid}))
            st.success("✅ Statement submitted successfully")
            if st.button("⬅ Back to Dashboard"):
                for k in ["statement_id", "product_index", "statement_year",
                           "statement_month", "selected_stockist_id", "engine_stage"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # Admin finalize
    if role == "admin" and not readonly:
        if st.button("✅ Admin Finalize Changes", type="primary"):
            safe_exec(
                admin_supabase.table("statements").update({
                    "status": "final",
                    "editing_by": None,
                    "editing_at": None,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", sid)
            )
            log_audit(
                action="admin_corrected_statement", target_type="statement", target_id=sid,
                performed_by=user_id,
                message="Admin corrected and finalized a submitted statement"
            )
            st.success("✅ Admin changes finalized successfully")
            if st.button("⬅ Back to Dashboard"):
                for k in ["statement_id", "product_index", "statement_year",
                           "statement_month", "selected_stockist_id", "engine_stage"]:
                    st.session_state.pop(k, None)
                st.rerun()


# ======================================================
# REPORTS — run_reports()
# ======================================================

def run_reports():
    st.title("📊 Reports & Matrices")
    user_id = st.session_state.auth_user.id
    role = st.session_state.get("role", "user")

    col1, col2, col3 = st.columns(3)

    with col1:
        if role == "admin":
            users = supabase.table("users").select("id, username").order("username").execute().data
            selected_users = st.multiselect("Users", users, default=users, format_func=lambda x: x["username"])
            visible_user_ids = [u["id"] for u in selected_users]
        else:
            my_profile = supabase.table("users").select("id, designation").eq("id", user_id).limit(1).execute().data[0]
            if my_profile["designation"] in ("manager", "senior_manager"):
                reps = supabase.table("users").select("id").eq("report_to", user_id).execute().data
                visible_user_ids = [user_id] + [r["id"] for r in reps]
            else:
                visible_user_ids = [user_id]
            st.text_input("User Scope", value="Auto (Hierarchy Based)", disabled=True)

    with col2:
        year_from = st.selectbox("Year From", list(range(2020, date.today().year + 1)))
        month_from = st.selectbox("Month From", list(range(1, 13)))

    with col3:
        year_to = st.selectbox("Year To", list(range(2020, date.today().year + 1)))
        month_to = st.selectbox("Month To", list(range(1, 13)))

    raw_stockists = supabase.table("user_stockists") \
        .select("stockist_id, stockists(name)") \
        .in_("user_id", visible_user_ids) \
        .execute().data

    stockists = [{"id": r["stockist_id"], "name": r["stockists"]["name"]} for r in raw_stockists]

    if not stockists:
        st.warning("No stockists available for your reporting scope")
        return

    selected_stockists = st.multiselect("Stockists", stockists, default=stockists, format_func=lambda x: x["name"])
    stockist_ids = [s["id"] for s in selected_stockists]

    summary_rows = safe_exec(
        admin_supabase.table("monthly_summary")
        .select("year, month, total_issue, total_closing, total_order, products(name), stockist_id")
        .in_("stockist_id", stockist_ids)
    )

    if not summary_rows:
        st.info("No data for selected filters")
        return

    df = pd.DataFrame([{
        "Product": r["products"]["name"],
        "Year-Month": f"{r['year']}-{r['month']:02d}",
        "Issue": r["total_issue"],
        "Closing": r["total_closing"],
        "Order": r["total_order"]
    } for r in summary_rows])

    if "drilldown_product" not in st.session_state:
        st.session_state.drilldown_product = None

    if st.session_state.drilldown_product:
        df = df[df["Product"] == st.session_state.drilldown_product]

    # Alerts
    st.subheader("🚨 Alerts Summary")
    df_sorted = df.sort_values(["Product", "Year-Month"])
    alert_found = False
    for product in df_sorted["Product"].unique():
        df_p = df_sorted[df_sorted["Product"] == product]
        if len(df_p) < 2:
            continue
        latest, previous = df_p.iloc[-1], df_p.iloc[-2]
        if latest["Issue"] < previous["Issue"]:
            alert_found = True
            if st.button(f"🔻 {product}: Issue degrowth", key=f"deg_{product}"):
                st.session_state.drilldown_product = product
                st.rerun()
        if latest["Issue"] > 0 and latest["Closing"] >= 2 * latest["Issue"]:
            alert_found = True
            if st.button(f"⚠️ {product}: High closing stock", key=f"stk_{product}"):
                st.session_state.drilldown_product = product
                st.rerun()
        if latest["Issue"] == 0 and latest["Closing"] == 0:
            alert_found = True
            if st.button(f"📣 {product}: Promotion needed", key=f"pro_{product}"):
                st.session_state.drilldown_product = product
                st.rerun()
    if not alert_found:
        st.success("✅ No alerts for selected period")

    if st.session_state.drilldown_product:
        st.info(f"🔍 Viewing detailed insights for **{st.session_state.drilldown_product}**")
        if st.button("⬅️ Back to All Products"):
            st.session_state.drilldown_product = None
            st.rerun()

    # Matrices
    st.subheader("📦 Stock Control Matrix")
    stockist_for_matrix = st.selectbox("Select Stockist (Required)", selected_stockists, format_func=lambda x: x["name"])
    m_year = st.selectbox("Year", sorted(set(df["Year-Month"].str[:4])))
    m_month = st.selectbox("Month", list(range(1, 13)))

    if stockist_for_matrix:
        stmt = safe_exec(
            admin_supabase.table("statements").select("id")
            .eq("stockist_id", stockist_for_matrix["id"])
            .eq("year", int(m_year)).eq("month", int(m_month))
            .eq("status", "final").limit(1)
        )
        if not stmt:
            st.warning("No final statement for selected period")
        else:
            stmt_id = stmt[0]["id"]
            rows = safe_exec(
                admin_supabase.table("statement_products")
                .select("opening,purchase,issue,closing,difference,order_qty,issue_guidance,stock_guidance,product_id,products!statement_products_product_id_fkey(name)")
                .eq("statement_id", stmt_id)
            )
            matrix = []
            for r in rows:
                last_closing = fetch_last_month_closing_only(stockist_for_matrix["id"], r["product_id"], int(m_year), int(m_month))
                matrix.append({
                    "Product": r["products"]["name"],
                    "Last Month Closing": last_closing,
                    "Opening": r["opening"],
                    "Closing": r["closing"],
                    "Issue Guidance": r["issue_guidance"],
                    "Stock Guidance": r["stock_guidance"],
                    "Order": r["order_qty"],
                    "Difference": r["difference"]
                })
            st.dataframe(pd.DataFrame(matrix).sort_values("Product"), use_container_width=True, hide_index=True)

    st.subheader("📦 Matrix 1 — Product-wise Sales (Issue)")
    st.dataframe(df.pivot_table(index="Product", columns="Year-Month", values="Issue", aggfunc="sum", fill_value=0), use_container_width=True)

    st.subheader("🧾 Matrix 2 — Product-wise Order")
    st.dataframe(df.pivot_table(index="Product", columns="Year-Month", values="Order", aggfunc="sum", fill_value=0), use_container_width=True)

    st.subheader("📊 Matrix 3 — Product-wise Closing")
    st.dataframe(df.pivot_table(index="Product", columns="Year-Month", values="Closing", aggfunc="sum", fill_value=0), use_container_width=True)

    st.subheader("📦📊 Matrix 4 — Issue & Closing")
    st.dataframe(
        df.melt(id_vars=["Product", "Year-Month"], value_vars=["Issue", "Closing"])
        .pivot_table(index="Product", columns=["Year-Month", "variable"], values="value", aggfunc="sum", fill_value=0),
        use_container_width=True
    )

    # Trend charts
    st.subheader("📈 Trend Charts — Last 6 Months")
    today = date.today()
    last_6 = []
    y, m = today.year, today.month
    for _ in range(6):
        last_6.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1

    df_trend = df[df["Year-Month"].isin(last_6)]
    if df_trend.empty:
        st.info("No trend data available for last 6 months")
    else:
        trend_products = sorted(df_trend["Product"].unique())
        default_index = 0
        if st.session_state.get("drilldown_product") in trend_products:
            default_index = trend_products.index(st.session_state.drilldown_product)
        trend_product = st.selectbox("Select Product for Trend", trend_products, index=default_index)
        chart_df = (
            df_trend[df_trend["Product"] == trend_product]
            .sort_values("Year-Month")
            .set_index("Year-Month")[["Issue", "Closing"]]
        )
        st.line_chart(chart_df)

    # Forecast
    st.subheader("🔮 Forecast — Next 3 Months")
    products_master = [p for p in load_products_cached() if "peak_months" in p]
    forecast_rows = []
    for p in products_master:
        df_p = df[df["Product"] == p["name"]]
        if df_p.empty:
            continue
        last_issue = df_p.sort_values("Year-Month").iloc[-1]["Issue"]
        fy, fm = today.year, today.month + 1
        if fm == 13:
            fm = 1
            fy += 1
        for _ in range(3):
            if fm in (p.get("peak_months") or []):
                factor = 2
            elif fm in (p.get("high_months") or []):
                factor = 1.5
            elif fm in (p.get("lowest_months") or []):
                factor = 0.8
            else:
                factor = 1
            forecast_rows.append({"Product": p["name"], "Forecast Month": f"{fy}-{fm:02d}", "Forecast Issue": round(last_issue * factor, 2)})
            fm += 1
            if fm == 13:
                fm = 1
                fy += 1

    if forecast_rows:
        st.dataframe(
            pd.DataFrame(forecast_rows).pivot_table(index="Product", columns="Forecast Month", values="Forecast Issue", fill_value=0),
            use_container_width=True
        )
    else:
        st.info("Forecast not available for selected filters")

    # KPI
    st.subheader("📊 KPI — Month-on-Month")
    kpi_df = df.groupby("Year-Month", as_index=False).agg({"Issue": "sum"}).sort_values("Year-Month")
    if len(kpi_df) >= 2:
        cur, prev = kpi_df.iloc[-1], kpi_df.iloc[-2]
        mom = cur["Issue"] - prev["Issue"]
        pct = (mom / prev["Issue"] * 100) if prev["Issue"] else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Current Issue", round(cur["Issue"], 2))
        c2.metric("MoM Change", round(mom, 2), round(mom, 2))
        c3.metric("Growth %", f"{round(pct, 2)}%", f"{round(pct, 2)}%")
    else:
        st.info("Not enough data for KPI")

    # Product KPI
    st.subheader("📊 Product-level KPI Cards")
    product_list = sorted(df["Product"].unique())
    selected_product = st.selectbox("Select Product", product_list)
    df_p = df[df["Product"] == selected_product].groupby("Year-Month", as_index=False).agg({"Issue": "sum"}).sort_values("Year-Month")
    if len(df_p) >= 2:
        latest, previous = df_p.iloc[-1], df_p.iloc[-2]
        mom = latest["Issue"] - previous["Issue"]
        pct = (mom / previous["Issue"] * 100) if previous["Issue"] else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Latest Issue", round(latest["Issue"], 2))
        c2.metric("Previous Issue", round(previous["Issue"], 2))
        c3.metric("MoM Change", round(mom, 2), round(mom, 2))
        c4.metric("Growth %", f"{round(pct, 2)}%", f"{round(pct, 2)}%")
    else:
        st.info("Not enough data for product KPI")

    # Authorized stockists panel
    st.divider()
    st.title("🏪 Authorized Stockists — Last Submitted Stock Control")
    if role == "admin":
        authorized_stockists = safe_exec(
            supabase.table("stockists").select("id, name").eq("authorization_status", "AUTHORIZED").order("name")
        )
    else:
        scoped = safe_exec(
            supabase.table("user_stockists")
            .select("stockist_id, stockists(id, name, authorization_status)")
            .in_("user_id", visible_user_ids)
        )
        authorized_stockists = list({
            r["stockists"]["id"]: {"id": r["stockists"]["id"], "name": r["stockists"]["name"]}
            for r in scoped
            if r["stockists"]["authorization_status"] == "AUTHORIZED"
        }.values())

    if not authorized_stockists:
        st.info("No authorized stockists found.")
        return

    for stockist in authorized_stockists:
        stockist_id = stockist["id"]
        last_stmt = safe_exec(
            admin_supabase.table("statements").select("id, year, month")
            .eq("stockist_id", stockist_id).eq("status", "final")
            .order("year", desc=True).order("month", desc=True).limit(1)
        )
        if not last_stmt:
            continue

        stmt_id, stmt_year, stmt_month = last_stmt[0]["id"], last_stmt[0]["year"], last_stmt[0]["month"]
        territory_rows = safe_exec(
            supabase.table("territory_stockists").select("territories(name)").eq("stockist_id", stockist_id)
        )
        territory_label = ", ".join(sorted({t["territories"]["name"] for t in territory_rows if t.get("territories")})) or "—"

        st.subheader(f"🏪 {stockist['name']}")
        st.caption(f"📍 Territory: {territory_label}  |  🗓 Last Submitted: {stmt_month:02d}/{stmt_year}")

        rows = safe_exec(
            admin_supabase.table("statement_products")
            .select("opening,issue,closing,difference,order_qty,issue_guidance,stock_guidance,product_id,products!statement_products_product_id_fkey(name)")
            .eq("statement_id", stmt_id)
        )
        if not rows:
            st.warning("No product data found for this statement.")
            continue

        flags = detect_red_flags(rows)
        if any(flags.values()):
            st.error("🔴 Red Flags Detected")
            if flags["overstock"]:
                st.markdown(f"• **Overstock ({len(flags['overstock'])})**: {', '.join(flags['overstock'])}")
            if flags["zero_issue"]:
                st.markdown(f"• **Zero Issue ({len(flags['zero_issue'])})**: {', '.join(flags['zero_issue'])}")
            if flags["mismatch"]:
                st.markdown(f"• **Data Mismatch ({len(flags['mismatch'])})**: {', '.join(flags['mismatch'])}")
        else:
            st.success("🟢 No red flags detected")

        overstock_count = len(flags["overstock"])
        zero_issue_count = len(flags["zero_issue"])
        st.info("🧠 AI Summary")
        if overstock_count == 0 and zero_issue_count == 0:
            summary = f"{stockist['name']}'s last submitted statement ({stmt_month:02d}/{stmt_year}) shows a stable stock position."
        elif overstock_count > 0:
            summary = f"{stockist['name']}'s latest statement indicates overstocking in {overstock_count} product(s)."
        elif zero_issue_count > 0:
            summary = f"Several products show zero issue despite available stock in {stockist['name']}'s latest statement."
        else:
            summary = f"Data inconsistencies present in the latest statement ({stmt_month:02d}/{stmt_year}). Review recommended."
        st.markdown(summary)

        matrix = []
        for r in rows:
            last_closing = fetch_last_month_closing_only(stockist_id, r["product_id"], stmt_year, stmt_month)
            matrix.append({
                "Product": r["products"]["name"],
                "Last Month Closing": last_closing,
                "Opening": r["opening"],
                "Closing": r["closing"],
                "Issue Guidance": r["issue_guidance"],
                "Stock Guidance": r["stock_guidance"],
                "Order": r["order_qty"],
                "Difference": r["difference"]
            })
        st.dataframe(pd.DataFrame(matrix).sort_values("Product"), use_container_width=True, hide_index=True)


# ======================================================
# ADMIN PANEL — run_admin_panel()
# ======================================================

def run_admin_panel():
    user_id = st.session_state.auth_user.id
    role = st.session_state.get("role", "user")
    section = st.session_state.get("admin_section")

    # If statement engine is active (admin edit), run it
    if st.session_state.get("statement_id") and st.session_state.get("engine_stage") in ("edit", "preview", "view"):
        run_statement()
        return

    st.title("🔧 Admin Dashboard")

    # ── Admin section selector (replaces sidebar) ────────────────
    ADMIN_SECTIONS = [
        "— Select Admin Section —",
        "Statements",
        "Users",
        "Create User",
        "Stockists",
        "Products",
        "Territories",
        "Reset User Password",
        "Audit Logs",
        "Lock / Unlock Statements",
        "Analytics",
    ]
    current_index = ADMIN_SECTIONS.index(section) if section in ADMIN_SECTIONS else 0
    selected = st.selectbox(
        "Admin Section",
        ADMIN_SECTIONS,
        index=current_index,
        key="admin_section_picker"
    )
    if selected != section:
        st.session_state.admin_section = selected if selected != "— Select Admin Section —" else None
        st.rerun()

    section = st.session_state.get("admin_section")

    if not section:
        st.info("☝️ Select an admin section from the dropdown above")
        return

    # ── STATEMENTS ──────────────────────────────────────────────
    if section == "Statements":
        st.subheader("📄 Statement Control Panel")
        rows = safe_exec(
            admin_supabase.table("statements")
            .select("id, year, month, status, locked, editing_by, updated_at, stockists(name), users(username)")
            .order("updated_at", desc=True)
        )
        if not rows:
            st.info("No statements available")
            return

        stmt = st.selectbox("Select Statement", rows, format_func=lambda x: (
            f"{x['stockists']['name']} | {x['month']}/{x['year']} | {x['users']['username']} | "
            f"{'LOCKED' if x['locked'] else x['status'].upper()}"
        ))

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button("👁 View"):
                st.session_state.statement_id = stmt["id"]
                st.session_state.engine_stage = "view"
                st.rerun()
        with col2:
            if st.button("✏️ Admin Edit"):
                stmt_ctx = safe_exec(
                    admin_supabase.table("statements").select("year, month, stockist_id")
                    .eq("id", stmt["id"]).limit(1)
                )[0]
                safe_exec(admin_supabase.table("statements").update({
                    "status": "admin_edit", "editing_by": user_id,
                    "editing_at": datetime.utcnow().isoformat()
                }).eq("id", stmt["id"]))
                st.session_state.statement_id = stmt["id"]
                st.session_state.statement_year = stmt_ctx["year"]
                st.session_state.statement_month = stmt_ctx["month"]
                st.session_state.selected_stockist_id = stmt_ctx["stockist_id"]
                st.session_state.product_index = 0
                st.session_state.engine_stage = "edit"
                st.rerun()
        with col3:
            if stmt["status"] == "final" and not stmt["locked"]:
                if st.button("🔒 Lock"):
                    safe_exec(admin_supabase.table("statements").update({
                        "locked": True, "locked_at": datetime.utcnow().isoformat(), "locked_by": user_id
                    }).eq("id", stmt["id"]))
                    st.success("Statement locked")
                    st.rerun()
        with col4:
            if stmt["locked"]:
                if st.button("🔓 Unlock"):
                    safe_exec(admin_supabase.table("statements").update({
                        "locked": False, "locked_at": None, "locked_by": None
                    }).eq("id", stmt["id"]))
                    st.success("Statement unlocked")
                    st.rerun()
        with col5:
            if st.button("🗑 Delete"):
                safe_exec(admin_supabase.table("statement_products").delete().eq("statement_id", stmt["id"]))
                safe_exec(admin_supabase.table("statements").delete().eq("id", stmt["id"]))
                log_audit(
                    action="delete_statement", target_type="statement", target_id=stmt["id"],
                    performed_by=user_id,
                    message=f"Admin deleted statement for {stmt['stockists']['name']} ({stmt['month']:02d}/{stmt['year']})",
                    metadata={"stockist_name": stmt["stockists"]["name"], "month": stmt["month"], "year": stmt["year"]}
                )
                st.success("Statement permanently deleted")
                st.rerun()

    # ── USERS ──────────────────────────────────────────────────
    elif section == "Users":
        st.subheader("👤 Edit User & Assign Stockists")
        users = supabase.table("users").select("id, username, role, is_active, designation, report_to, phone, email").order("username").execute().data
        user = st.selectbox("Select User", users, format_func=lambda x: x["username"])
        is_active = st.checkbox("Active", value=user["is_active"])
        designation = st.radio("Designation", ["representative", "manager", "senior_manager", "office_staff"],
                                index=["representative", "manager", "senior_manager", "office_staff"].index(user.get("designation", "representative")), horizontal=True)
        manager_options = [u for u in users if u["role"] == "admin" or u.get("designation") in ("manager", "senior_manager")]
        report_to_ids = [u["id"] for u in manager_options]
        default_index = report_to_ids.index(user["report_to"]) if user.get("report_to") in report_to_ids else None
        report_to = st.selectbox("Reports To", manager_options, format_func=lambda x: x["username"], index=default_index)
        phone = st.text_input("Phone Number", value=user.get("phone") or "")
        email = st.text_input("Email ID", value=user.get("email") or "")
        all_stockists = supabase.table("stockists").select("id, name").order("name").execute().data
        assigned = supabase.table("user_stockists").select("stockist_id").eq("user_id", user["id"]).execute().data
        assigned_ids = [a["stockist_id"] for a in assigned]
        selected_stockists = st.multiselect("Assigned Stockists", all_stockists,
                                             default=[s for s in all_stockists if s["id"] in assigned_ids],
                                             format_func=lambda x: x["name"])
        if st.button("Save Changes"):
            supabase.table("users").update({
                "is_active": is_active, "designation": designation,
                "report_to": report_to["id"], "phone": phone.strip(),
                "email": email.strip(), "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user["id"]).execute()
            supabase.table("user_stockists").delete().eq("user_id", user["id"]).execute()
            for s in selected_stockists:
                supabase.table("user_stockists").insert({"user_id": user["id"], "stockist_id": s["id"]}).execute()
            log_audit(action="update_user", target_type="user", target_id=user["id"], performed_by=user_id,
                      message=f"User '{user['username']}' updated",
                      metadata={"is_active": is_active, "assigned_stockists": [s["name"] for s in selected_stockists]})
            st.success("User updated successfully")

    # ── CREATE USER ────────────────────────────────────────────
    elif section == "Create User":
        st.subheader("➕ Create User")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Create User"):
            email = f"{username}@internal.local"
            auth_user = admin_supabase.auth.admin.create_user({"email": email, "password": password, "email_confirm": True})
            supabase.table("users").insert({"id": auth_user.user.id, "username": username, "role": "user", "is_active": True}).execute()
            st.success("User created successfully")

    # ── STOCKISTS ──────────────────────────────────────────────
    elif section == "Stockists":
        st.subheader("🏪 Stockists")
        st.markdown("### ➕ Add Stockist")
        name = st.text_input("Stockist Name *")
        location = st.text_input("Location")
        phone = st.text_input("Phone Number", value="9433245464")
        payment_terms = st.number_input("Payment Terms (Days)", min_value=0, step=1)
        contact_person = st.text_input("Contact Person", value="")
        alternate_phone = st.text_input("Alternate Phone", value="")
        email = st.text_input("Email ID", value="")
        authorization_status = st.radio("Authorization Status", ["AUTHORIZED", "NONAUTHORIZED"], horizontal=True)
        otp_required = st.radio("OTP Requirement", ["OTP NOT NECESSARY", "OTP NECESSARY"], index=0, horizontal=True)
        if st.button("Add Stockist"):
            if not name.strip():
                st.error("Stockist name is required")
                return
            supabase.table("stockists").insert({
                "name": name.strip(), "location": location.strip() or None,
                "phone": phone.strip(), "contact_person": contact_person.strip(),
                "alternate_phone": alternate_phone.strip(), "email": email.strip(),
                "payment_terms": payment_terms or None,
                "authorization_status": authorization_status,
                "otp_required": otp_required == "OTP NECESSARY",
                "created_by": user_id
            }).execute()
            log_audit(action="create_stockist", target_type="stockist", performed_by=user_id,
                      message=f"Stockist '{name.strip()}' created")
            st.cache_data.clear()
            st.success("Stockist added successfully")
            st.rerun()

        st.divider()
        st.markdown("### ✏️ Edit Stockist")
        stockists = load_stockists_cached()
        if not stockists:
            st.info("No stockists available")
            return
        stockist = st.selectbox("Select Stockist", stockists, format_func=lambda x: x["name"])
        # Reload full stockist record for editing
        full = supabase.table("stockists").select("*").eq("id", stockist["id"]).limit(1).execute().data
        full = full[0] if full else {}
        edit_name = st.text_input("Edit Name", value=full.get("name", ""))
        edit_remarks = st.text_area("📝 Remarks", value=full.get("remarks") or "", height=100)
        edit_location = st.text_input("Edit Location", value=full.get("location") or "")
        edit_phone = st.text_input("Edit Phone", value=full.get("phone") or "")
        edit_contact_person = st.text_input("Contact Person", value=full.get("contact_person") or "", key=f"cp_{stockist['id']}")
        edit_alt_phone = st.text_input("Alternate Phone", value=full.get("alternate_phone") or "", key=f"ap_{stockist['id']}")
        edit_email = st.text_input("Email ID", value=full.get("email") or "", key=f"em_{stockist['id']}")
        edit_payment_terms = st.number_input("Edit Payment Terms (Days)", min_value=0, step=1, value=full.get("payment_terms") or 0)
        edit_auth = st.radio("Authorization Status", ["AUTHORIZED", "NONAUTHORIZED"],
                              index=0 if full.get("authorization_status", "AUTHORIZED") == "AUTHORIZED" else 1,
                              horizontal=True, key=f"auth_{stockist['id']}")
        edit_otp = st.radio("OTP Requirement", ["OTP NOT NECESSARY", "OTP NECESSARY"],
                             index=1 if full.get("otp_required") else 0,
                             horizontal=True, key=f"otp_{stockist['id']}")
        if st.button("Save Changes"):
            supabase.table("stockists").update({
                "name": edit_name.strip(), "location": edit_location.strip() or None,
                "phone": edit_phone.strip(), "contact_person": edit_contact_person.strip(),
                "alternate_phone": edit_alt_phone.strip(), "email": edit_email.strip(),
                "payment_terms": edit_payment_terms or None, "remarks": edit_remarks.strip() or None,
                "authorization_status": edit_auth, "otp_required": edit_otp == "OTP NECESSARY"
            }).eq("id", stockist["id"]).execute()
            st.cache_data.clear()
            st.success("Stockist updated successfully")
            st.rerun()

        st.divider()
        st.markdown("### 🗑 Delete Stockist")
        if st.button("Delete Stockist"):
            used_in_stmts = supabase.table("statements").select("id").eq("stockist_id", stockist["id"]).limit(1).execute().data
            used_in_users = supabase.table("user_stockists").select("user_id").eq("stockist_id", stockist["id"]).limit(1).execute().data
            if used_in_stmts:
                st.error("❌ Stockist is used in statements — cannot delete")
            elif used_in_users:
                st.error("❌ Stockist is assigned to users — unassign users first")
            else:
                supabase.table("stockists").delete().eq("id", stockist["id"]).execute()
                st.cache_data.clear()
                st.success("✅ Stockist deleted successfully")
                st.rerun()

    # ── PRODUCTS ───────────────────────────────────────────────
    elif section == "Products":
        st.subheader("📦 Products")
        name = st.text_input("Product Name")
        peak = st.multiselect("Peak Months", list(range(1, 13)))
        high = st.multiselect("High Months", list(range(1, 13)))
        low = st.multiselect("Low Months", list(range(1, 13)))
        lowest = st.multiselect("Lowest Months", list(range(1, 13)))
        composition = st.text_area("Composition", value="medicine")
        if st.button("Add Product"):
            supabase.table("products").insert({
                "name": name.strip(), "composition": composition.strip(),
                "peak_months": peak, "high_months": high, "low_months": low, "lowest_months": lowest
            }).execute()
            st.cache_data.clear()
            st.success("Product added")
            st.rerun()
        st.divider()
        products = load_products_cached()
        product = st.selectbox("Select Product", products, format_func=lambda x: x["name"])
        edit_name = st.text_input("Edit Name", value=product["name"])
        edit_composition = st.text_area("Composition", value=product.get("composition") or "medicine")
        if st.button("Update Product"):
            supabase.table("products").update({"name": edit_name.strip(), "composition": edit_composition.strip()}).eq("id", product["id"]).execute()
            st.cache_data.clear()
            st.success("Product updated")
            st.rerun()
        if st.button("Delete Product"):
            used = supabase.table("statement_products").select("id").eq("product_id", product["id"]).limit(1).execute().data
            if used:
                st.error("Product used in statements")
            else:
                supabase.table("products").delete().eq("id", product["id"]).execute()
                st.cache_data.clear()
                st.success("Product deleted")
                st.rerun()

    # ── TERRITORIES ────────────────────────────────────────────
    elif section == "Territories":
        st.subheader("📍 Territory Management")
        st.markdown("### ➕ Create Territory")
        t_name = st.text_input("Territory Name *")
        t_desc = st.text_area("Description")
        t_active = st.checkbox("Active", value=True)
        if st.button("Add Territory"):
            if not t_name.strip():
                st.error("Territory name is required")
                return
            supabase.table("territories").insert({"name": t_name.strip(), "description": t_desc.strip() or None, "is_active": t_active, "created_by": user_id}).execute()
            log_audit(action="create_territory", target_type="territory", performed_by=user_id, message=f"Territory '{t_name.strip()}' created")
            st.success("Territory created")
            st.rerun()

        st.divider()
        st.markdown("### ✏️ Edit Territory")
        territories = supabase.table("territories").select("*").order("name").execute().data
        if not territories:
            st.info("No territories available")
            return
        territory = st.selectbox("Select Territory", territories, format_func=lambda x: x["name"])
        edit_name = st.text_input("Edit Name", value=territory["name"])
        edit_desc = st.text_area("Edit Description", value=territory.get("description") or "")
        edit_active = st.checkbox("Active", value=territory["is_active"], key=f"tact_{territory['id']}")
        if st.button("Save Territory Changes"):
            supabase.table("territories").update({
                "name": edit_name.strip(), "description": edit_desc.strip() or None,
                "is_active": edit_active, "updated_at": datetime.utcnow().isoformat()
            }).eq("id", territory["id"]).execute()
            log_audit(action="update_territory", target_type="territory", target_id=territory["id"], performed_by=user_id, message=f"Territory '{edit_name.strip()}' updated")
            st.success("Territory updated")
            st.rerun()

        st.divider()
        st.markdown("### 👤 Assign Users")
        users = supabase.table("users").select("id, username").order("username").execute().data
        assigned_u = supabase.table("user_territories").select("user_id").eq("territory_id", territory["id"]).execute().data
        assigned_u_ids = [a["user_id"] for a in assigned_u]
        selected_users = st.multiselect("Users", users, default=[u for u in users if u["id"] in assigned_u_ids], format_func=lambda x: x["username"])
        if st.button("Save User Assignment"):
            supabase.table("user_territories").delete().eq("territory_id", territory["id"]).execute()
            for u in selected_users:
                supabase.table("user_territories").insert({"territory_id": territory["id"], "user_id": u["id"], "assigned_by": user_id}).execute()
            st.success("Users assigned")

        st.divider()
        st.markdown("### 🏪 Assign Stockists")
        stockists = supabase.table("stockists").select("id, name").order("name").execute().data
        assigned_s = supabase.table("territory_stockists").select("stockist_id").eq("territory_id", territory["id"]).execute().data
        assigned_s_ids = [s["stockist_id"] for s in assigned_s]
        selected_stockists = st.multiselect("Stockists", stockists, default=[s for s in stockists if s["id"] in assigned_s_ids], format_func=lambda x: x["name"])
        if st.button("Save Stockist Assignment"):
            supabase.table("territory_stockists").delete().eq("territory_id", territory["id"]).execute()
            for s in selected_stockists:
                supabase.table("territory_stockists").insert({"territory_id": territory["id"], "stockist_id": s["id"], "assigned_by": user_id}).execute()
            st.success("Stockists assigned")

    # ── RESET PASSWORD ─────────────────────────────────────────
    elif section == "Reset User Password":
        st.subheader("🔐 Reset User Password")
        users = supabase.table("users").select("id, username").order("username").execute().data
        u = st.selectbox("User", users, format_func=lambda x: x["username"])
        pwd = st.text_input("New Password", type="password")
        if st.button("Reset Password"):
            if not pwd.strip():
                st.error("Password cannot be empty")
                return
            if len(pwd) < 8:
                st.error("❌ Password must be at least 8 characters long")
                return
            try:
                admin_supabase.auth.admin.update_user_by_id(u["id"], {"password": pwd})
                log_audit(action="reset_user_password", target_type="user", target_id=u["id"], performed_by=user_id, message=f"Password reset for user '{u['username']}'")
                st.success("✅ Password reset successfully")
            except Exception as e:
                st.error("❌ Password rejected by security policy")
                st.exception(e)

    # ── AUDIT LOGS ─────────────────────────────────────────────
    elif section == "Audit Logs":
        st.subheader("📜 Audit Logs")
        f1, f2, f3 = st.columns(3)
        with f1:
            actions = supabase.table("audit_logs").select("action").execute().data
            action_options = sorted(set(a["action"] for a in actions if a["action"]))
            selected_actions = st.multiselect("Action", action_options, default=action_options)
        with f2:
            users = supabase.table("users").select("id, username").order("username").execute().data
            user_map = {u["id"]: u["username"] for u in users}
            selected_log_users = st.multiselect("Performed By", users, format_func=lambda x: x["username"])
            selected_user_ids = [u["id"] for u in selected_log_users]
        with f3:
            days = st.selectbox("Time Range", [1, 3, 7, 30, 90, 365], index=3)

        query = supabase.table("audit_logs").select("*") \
            .gte("created_at", (datetime.utcnow() - timedelta(days=days)).isoformat()) \
            .order("created_at", desc=True)
        if selected_actions:
            query = query.in_("action", selected_actions)
        if selected_user_ids:
            query = query.in_("performed_by", selected_user_ids)
        logs = query.execute().data

        if not logs:
            st.info("No audit logs found for selected filters")
            return
        for log in logs:
            with st.expander(f"🕒 {log['created_at']} — {log['action']}", expanded=False):
                st.markdown(f"**Message:** {log.get('message', '—')}")
                st.markdown(f"**Performed By:** {user_map.get(log['performed_by'], 'Unknown')}")
                st.markdown(f"**Target Type:** {log.get('target_type')}")
                st.markdown(f"**Target ID:** `{log.get('target_id')}`")
                if log.get("metadata"):
                    st.json(log["metadata"])

    # ── LOCK / UNLOCK ──────────────────────────────────────────
    elif section == "Lock / Unlock Statements":
        stmts = supabase.table("statements").select("*").execute().data
        if not stmts:
            st.info("No statements available")
            return
        s = st.selectbox("Statement", stmts, format_func=lambda x: f"{x['year']}-{x['month']} | {x['status']}")
        if st.button("Lock", key="lock_statement_btn"):
            supabase.table("statements").update({"status": "locked", "locked_at": datetime.utcnow().isoformat(), "locked_by": user_id}).eq("id", s["id"]).execute()
            st.success("Statement locked")
            st.rerun()
        if st.button("Unlock", key="unlock_statement_btn"):
            supabase.table("statements").update({"status": "draft", "locked_at": None, "locked_by": None}).eq("id", s["id"]).execute()
            st.success("Statement unlocked")
            st.rerun()

    # ── ANALYTICS ─────────────────────────────────────────────
    elif section == "Analytics":
        st.subheader("📊 Monthly Analytics")
        years = sorted(set(r["year"] for r in supabase.table("monthly_summary").select("year").execute().data))
        if not years:
            st.info("No data available")
            return
        year = st.selectbox("Year", years)
        month = st.selectbox("Month", list(range(1, 13)))
        stockists = supabase.table("stockists").select("id, name").order("name").execute().data
        stockist = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])
        rows = supabase.table("monthly_summary") \
            .select("total_issue, total_closing, total_order, products(name)") \
            .eq("year", year).eq("month", month).eq("stockist_id", stockist["id"]) \
            .execute().data
        if rows:
            df = pd.DataFrame([{"Product": r["products"]["name"], "Issue": r["total_issue"], "Closing": r["total_closing"], "Order": r["total_order"]} for r in rows])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No data for selected period")
