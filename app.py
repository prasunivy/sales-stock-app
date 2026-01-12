import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta


# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="Ivy Pharmaceuticals",
    layout="wide",
    initial_sidebar_state="expanded"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

admin_supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
)

# ======================================================
# ======================================================
# SESSION STATE
# ======================================================
for k in [
    "auth_user",
    "role",
    "statement_id",
    "product_index",
    "statement_year",
    "statement_month",
    "selected_stockist_id",
    "engine_stage",
    "admin_section"

]:
    if k not in st.session_state:
        st.session_state[k] = None


# ======================================================
# SAFE EXEC
# ======================================================
def safe_exec(q, msg="Database error"):
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


# ======================================================
# CACHED DATA LOADERS (STEP 1 — PERFORMANCE OPTIMIZATION)
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
    if month == 1:
        return year - 1, 12
    return year, month - 1


def fetch_last_month_data(stockist_id, product_id, year, month):
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


# ======================================================
# AUTH HELPERS
# ======================================================
def username_to_email(username):
    rows = safe_exec(
        supabase.table("users")
        .select("id,is_active")
        .eq("username", username)
    )
    if not rows or not rows[0]["is_active"]:
        return None
    return f"{username}@internal.local"


def login(username, password):
    email = username_to_email(username)
    if not email:
        raise Exception("Invalid or inactive user")
    return supabase.auth.sign_in_with_password(
        {"email": email, "password": password}
    )


def load_profile(uid):
    return safe_exec(
        supabase.table("users")
        .select("*")
        .eq("id", uid)
    )[0]
# ======================================================
# AUDIT LOG HELPER
# ======================================================
def log_audit(
    *,
    action: str,
    message: str,
    performed_by: str,
    target_type: str = None,
    target_id: str = None,
    metadata: dict = None
):
    # Resolve username (best-effort)
    username = None
    try:
        u = supabase.table("users") \
            .select("username") \
            .eq("id", performed_by) \
            .limit(1) \
            .execute().data
        if u:
            username = u[0]["username"]
    except Exception:
        pass

    enriched_metadata = metadata or {}
    enriched_metadata["performed_by_username"] = username

    supabase.table("audit_logs").insert({
        "action": action,
        "message": message,
        "performed_by": performed_by,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": enriched_metadata
    }).execute()


# ======================================================
# LOGIN
# ======================================================
if not st.session_state.auth_user:
    st.title("🔐 Login")
    st.title("Ivy Pharmaceuticals")
    st.caption("Sales & Stock Management System")
    st.divider()
    st.subheader("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            auth = login(username, password)
            profile = load_profile(auth.user.id)

            st.session_state.auth_user = auth.user
            st.session_state.role = profile["role"]

            # 🔥 RESET ENGINE STATE ON LOGIN (CRITICAL FIX)
            st.session_state.engine_stage = None
            st.session_state.admin_section = None
            st.session_state.statement_id = None
            st.session_state.product_index = None
            st.session_state.statement_year = None
            st.session_state.statement_month = None
            st.session_state.selected_stockist_id = None

            st.rerun()
        except Exception as e:
            st.error(str(e))


    st.stop()

# ======================================================
# AFTER LOGIN SUCCESS
# ======================================================
role = st.session_state.role
user_id = st.session_state.auth_user.id

# ======================================================
# SIDEBAR
# ======================================================
st.sidebar.title("Navigation")
# ------------------------------
# COMMON NAVIGATION
# ------------------------------
if st.sidebar.button("📊 Reports", key="nav_reports"):
    st.session_state.engine_stage = "reports"
    st.session_state.admin_section = None
    st.rerun()
# ======================================================
# USER SIDEBAR — STATEMENTS
# ======================================================
if role == "user":

    st.sidebar.divider()
    st.sidebar.subheader("🗂 My Statements")

    # --------------------------------------------------
    # STOCKIST DROPDOWN FILTER (REPLACES SEARCH BOX)
    # --------------------------------------------------
    stockist_rows = safe_exec(
        admin_supabase.table("statements")
        .select("stockist_id, stockists(name)")
        .eq("user_id", user_id)
    )

    stockist_options = {
        r["stockist_id"]: r["stockists"]["name"]
        for r in stockist_rows
    }

    selected_stockist_id = st.sidebar.selectbox(
        "Select Stockist",
        options=[None] + list(stockist_options.keys()),
        format_func=lambda x: "— All Stockists —" if x is None else stockist_options[x]
    )


    my_statements = admin_supabase.table("statements") \
        .select(
            "id, year, month, status, locked, current_product_index, stockist_id, stockists(name)"
        ) \
        .eq("user_id", user_id) \
        .order("year", desc=True) \
        .order("month", desc=True) \
        .execute().data

    if not my_statements:
        st.sidebar.info("No statements yet")
    else:
        total_products = len(load_products_cached())

        for s in my_statements:

            # Filter by selected stockist
            if selected_stockist_id and s["stockist_id"] != selected_stockist_id:
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

            if st.sidebar.button(
                f"👁 View • {label}",
                key=f"user_stmt_{s['id']}"
            ):
                st.session_state.statement_id = s["id"]
                st.session_state.product_index = s.get("current_product_index") or 0
                st.session_state.statement_year = s["year"]
                st.session_state.statement_month = s["month"]
                st.session_state.selected_stockist_id = s["stockist_id"]
                st.session_state.engine_stage = action
                st.rerun()

                


    # --------------------------------------------------
    # ➕ CREATE / RESUME NEW STATEMENT
    # --------------------------------------------------
    st.sidebar.divider()
    st.sidebar.subheader("➕ New Statement")

    stockists = safe_exec(
        supabase.table("user_stockists")
        .select("stockist_id, stockists(name)")
        .eq("user_id", user_id)
    )

    if not stockists:
        st.sidebar.error(
            "❌ No stockists assigned to your user.\n\n"
            "Please contact admin to assign stockists."
        )
        st.stop()


    if stockists:
        selected = st.sidebar.selectbox(
            "Stockist",
            stockists,
            format_func=lambda x: x["stockists"]["name"]
        )

        today = date.today()
        year = st.sidebar.selectbox("Year", [today.year - 1, today.year])
        month = st.sidebar.selectbox(
            "Month",
            list(range(1, today.month + 1)) if year == today.year else list(range(1, 13))
        )

        if st.sidebar.button("➕ Create / Resume"):

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

            # 🚫 Locked check
            if stmt["locked"]:
                st.sidebar.error("Statement is locked by admin")
                st.stop()

            # 🚫 Another editor check
            if stmt.get("editing_by") and stmt["editing_by"] != user_id:
                st.sidebar.error("Statement is open on another device")
                st.stop()

            # ✅ Acquire lock
            safe_exec(
                admin_supabase.table("statements")
                .update({
                    "editing_by": user_id,
                    "editing_at": datetime.utcnow().isoformat(),
                    "last_saved_at": datetime.utcnow().isoformat()
                })
                .eq("id", stmt["id"])
            )

            # ✅ Move user into editor (SET ALL REQUIRED STATE)
            st.session_state.statement_id = stmt["id"]
            st.session_state.product_index = stmt.get("current_product_index") or 0
            st.session_state.statement_year = stmt["year"]
            st.session_state.statement_month = stmt["month"]
            st.session_state.selected_stockist_id = stmt["stockist_id"]
            st.session_state.engine_stage = "edit"


            st.rerun()

    else:
        st.sidebar.warning("No stockists assigned")

if role == "admin":

    st.sidebar.markdown("### 🛠 Admin")
    # --------------------------------------------------
    # 🧪 ADMIN DEBUG PANEL (TEMPORARY)
    # --------------------------------------------------
    with st.sidebar.expander("🧪 Debug (Session State)", expanded=False):
        st.write("role:", st.session_state.get("role"))
        st.write("engine_stage:", st.session_state.get("engine_stage"))
        st.write("admin_section:", st.session_state.get("admin_section"))
        st.write("statement_id:", st.session_state.get("statement_id"))
        st.write("product_index:", st.session_state.get("product_index"))
        st.write("statement_year:", st.session_state.get("statement_year"))
        st.write("statement_month:", st.session_state.get("statement_month"))
        st.write("selected_stockist_id:", st.session_state.get("selected_stockist_id"))

    if st.sidebar.button("📄 Statements", key="admin_nav_statements"):
        st.session_state.admin_section = "Statements"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("👤 Users", key="admin_nav_users"):
        st.session_state.admin_section = "Users"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("➕ Create User", key="admin_nav_create_user"):
        st.session_state.admin_section = "Create User"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("🏪 Stockists", key="admin_nav_stockists"):
        st.session_state.admin_section = "Stockists"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("📦 Products", key="admin_nav_products"):
        st.session_state.admin_section = "Products"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("🔐 Reset User Password", key="admin_nav_reset_pwd"):
        st.session_state.admin_section = "Reset User Password"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("📜 Audit Logs", key="admin_nav_audit"):
        st.session_state.admin_section = "Audit Logs"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("🔒 Lock / Unlock Statements", key="admin_nav_lock"):
        st.session_state.admin_section = "Lock / Unlock Statements"
        st.session_state.engine_stage = None
        st.rerun()

    if st.sidebar.button("📈 Analytics", key="admin_nav_analytics"):
        st.session_state.admin_section = "Analytics"
        st.session_state.engine_stage = None
        st.rerun()





if st.sidebar.button("Logout"):

    if st.session_state.get("statement_id"):
        safe_exec(
            admin_supabase.table("statements")
            .update({
                "editing_by": None,
                "editing_at": None,
                "updated_at": datetime.utcnow().isoformat()
            })
            .eq("id", st.session_state.statement_id)
            .eq("editing_by", user_id)
        )

    st.session_state.clear()
    st.rerun()


# ======================================================
# USER LANDING (MAIN PAGE — USER)
# ======================================================
if role == "user":

    if not st.session_state.statement_id:

        st.title("📊 Sales & Stock Statement")

        st.markdown(
            """
            ### 👈 Start from the Sidebar

            Use the **left sidebar** to manage your statements:

            **You can:**
            - ▶ Resume a draft statement
            - 👁 View a submitted or locked statement
            - ➕ Create a new statement by selecting:
              - Stockist
              - Year
              - Month

            ---
            """
        )

        st.info(
            "ℹ️ Draft statements are saved automatically. "
            "You can safely close the app and resume later."
        )

        st.stop()


# ======================================================
# PRODUCT ENGINE
# ======================================================
# SAFETY CHECK — REQUIRED STATE
required_keys = [
    "statement_id",
    "statement_year",
    "statement_month",
    "selected_stockist_id"
]

# SAFETY CHECK — REQUIRED STATE (USER ONLY)
if role == "user":

    if not all(st.session_state.get(k) is not None for k in required_keys):
        st.error("❌ Statement context incomplete. Please restart from sidebar.")
        st.stop()


if (
    role == "user"
    and st.session_state.statement_id
    and st.session_state.engine_stage == "edit"
):

    sid = st.session_state.statement_id
    idx = st.session_state.product_index

    products = load_products_cached()
    # ======================================================
    # 🧹 RESET STATEMENT (USER SAFETY ACTION)
    # ======================================================
    stmt_meta = safe_exec(
        admin_supabase.table("statements")
        .select("status, locked, stockist_id, year, month")
        .eq("id", sid)
        .limit(1)
    )

    stmt_meta = stmt_meta[0]

    # Show reset option ONLY for editable drafts
    if stmt_meta["status"] == "draft" and not stmt_meta["locked"]:

        with st.expander("🧹 Reset Statement (start over)", expanded=False):

            st.warning(
                "⚠️ This will permanently delete the current statement and all entered "
                "product data.\n\n"
                "You will be returned to the Stockist / Year / Month selection screen.\n\n"
                "**This action cannot be undone.**"
            )

            confirm_reset = st.checkbox(
                "I understand and want to reset this statement"
            )

            if st.button(
                "🧹 Reset Statement Now",
                disabled=not confirm_reset,
                type="primary"
            ):

                # 1️⃣ Delete statement products
                safe_exec(
                    admin_supabase.table("statement_products")
                    .delete()
                    .eq("statement_id", sid)
                )

                # 2️⃣ Delete statement itself
                safe_exec(
                    admin_supabase.table("statements")
                    .delete()
                    .eq("id", sid)
                    .eq("user_id", user_id)
                )

                # 3️⃣ Audit log
                # 3️⃣ Audit log (human + developer friendly)
                stockist_row = supabase.table("stockists") \
                    .select("name") \
                    .eq("id", stmt_meta["stockist_id"]) \
                    .limit(1) \
                    .execute().data

                stockist_name = stockist_row[0]["name"] if stockist_row else "Unknown Stockist"

                log_audit(
                    action="reset_statement",
                    target_type="statement",
                    target_id=sid,
                    performed_by=user_id,
                    message=(
                        f"Statement reset for stockist "
                        f"{stockist_name} "
                        f"({stmt_meta['month']:02d}/{stmt_meta['year']})"
                    ),
                    metadata={
                        "stockist_id": stmt_meta["stockist_id"],
                        "stockist_name": stockist_name,
                        "year": stmt_meta["year"],
                        "month": stmt_meta["month"]
                    }
                )


                # 4️⃣ Clear engine session state
                for k in [
                    "statement_id",
                    "product_index",
                    "statement_year",
                    "statement_month",
                    "selected_stockist_id",
                    "engine_stage"
                ]:
                    st.session_state.pop(k, None)

                st.success("✅ Statement reset successfully. You can start again.")
                st.rerun()

    

    if idx >= len(products):
        st.session_state.engine_stage = "preview"
        st.rerun()

    product = products[idx]

    # --------------------------------------------------
    # HEADER
    # --------------------------------------------------
    st.subheader(f"Product {idx + 1} of {len(products)} — {product['name']}")

    # 💾 Last saved banner (statement-level ONLY)
    stmt_meta = safe_exec(
        admin_supabase.table("statements")
        .select("last_saved_at")
        .eq("id", sid)
        .limit(1)
    )

    if stmt_meta and stmt_meta[0]["last_saved_at"]:
        st.caption(f"💾 Last saved at {stmt_meta[0]['last_saved_at']}")
    else:
        st.caption("💾 Not saved yet")

    # --------------------------------------------------
    # FETCH EXISTING DRAFT ROW
    # --------------------------------------------------
    row = safe_exec(
        admin_supabase.table("statement_products")
        .select("*")
        .eq("statement_id", sid)
        .eq("product_id", product["id"])
        .limit(1)
    )
    row = row[0] if row else {}

    # --------------------------------------------------
    # LAST MONTH DATA
    # --------------------------------------------------
    last_closing, last_issue = fetch_last_month_data(
        st.session_state.selected_stockist_id,
        product["id"],
        st.session_state.statement_year,
        st.session_state.statement_month
    )

    # --------------------------------------------------
    # INPUT FIELDS
    # --------------------------------------------------
    opening = st.number_input(
        "Opening",
        step=1,
        format="%d",
        value=int(row.get("opening", last_closing)),
        key=f"opening_{sid}_{product['id']}"
    )

    st.caption(f"Last Month Issue: {last_issue}")

    purchase = st.number_input(
        "Purchase",
        step=1,
        format="%d",
        value=int(row.get("purchase", 0)),
        key=f"purchase_{sid}_{product['id']}"
    )

    issue = st.number_input(
        "Issue",
        step=1,
        format="%d",
        value=int(row.get("issue", 0)),
        key=f"issue_{sid}_{product['id']}"
    )

    calculated_closing = opening + purchase - issue

    closing = st.number_input(
        "Closing",
        step=1,
        format="%d",
        value=int(row.get("closing", calculated_closing)),
        key=f"closing_{sid}_{product['id']}"
    )


    diff = calculated_closing - closing
    if diff != 0:
        st.warning(f"Difference detected: {diff}")

    # --------------------------------------------------
    # GUIDANCE & ORDER (FROM SQL TRIGGER)
    # --------------------------------------------------
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

    # --------------------------------------------------
    # NAVIGATION
    # --------------------------------------------------
    c1, c2 = st.columns(2)

    if c1.button("⬅ Previous", disabled=(idx == 0)):
        st.session_state.product_index -= 1
        st.rerun()

    if c2.button("💾 Save & Next"):
        safe_exec(
            admin_supabase.table("statement_products").upsert(
                {
                    "statement_id": sid,
                    "product_id": product["id"],
                    "opening": int(opening),
                    "last_month_issue": int(last_issue),
                    "purchase": int(purchase),
                    "issue": int(issue),
                    "closing": int(closing),
                    "calculated_closing": calculated_closing,
                    "updated_at": datetime.utcnow().isoformat()
                },
                on_conflict="statement_id,product_id"
            )
        )

        st.session_state.product_index += 1

        safe_exec(
            admin_supabase.table("statements")
            .update({
                "current_product_index": st.session_state.product_index,
                "last_saved_at": datetime.utcnow().isoformat()
            })
            .eq("id", sid)
        )

        st.rerun()


# ======================================================
# PREVIEW & EDIT JUMP
# ======================================================
if (
    st.session_state.statement_id
    and st.session_state.engine_stage in ("preview", "view")
):

    sid = st.session_state.statement_id
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

    df = pd.DataFrame(
        [
            {
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
            }
            for r in rows
        ]
    )

    if "Product ID" in df.columns:
        st.dataframe(df.drop(columns=["Product ID"]), use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)
    # --------------------------------------------------
    # 🕒 STATEMENT TIMELINE
    # --------------------------------------------------
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
            st.markdown(
                f"🕒 **{log['created_at']}** — "
                f"{log.get('message') or log['action']}"
            )

            if log.get("metadata"):
                with st.expander("Details", expanded=False):
                    st.json(log["metadata"])


    # --------------------------------------------------
    # PREVIEW → EDIT JUMP
    # --------------------------------------------------
    if not readonly and rows:

        st.subheader("✏️ Edit a Product")

        product_options = [
            (r["products"]["name"], r["product_id"])
            for r in rows
        ]

        selected = st.selectbox(
            "Select product to edit",
            product_options,
            format_func=lambda x: x[0]
        )

        if st.button("✏️ Edit Selected Product"):

            product_index_map = {
                p["id"]: idx
                for idx, p in enumerate(
                    safe_exec(
                        supabase.table("products")
                        .select("id")
                        .order("name")
                    )
                )
            }

            st.session_state.product_index = product_index_map[selected[1]]
            st.session_state.engine_stage = "edit"
            st.rerun()

# ======================================================
# FINAL SUBMIT
# ======================================================
if (
    role == "user"
    and st.session_state.statement_id
    and st.session_state.engine_stage == "preview"
):

    total_products = len(
        safe_exec(
            supabase.table("products").select("id")
        )
    )

    entered_products = len(
        safe_exec(
            admin_supabase.table("statement_products")
            .select("product_id")
            .eq("statement_id", st.session_state.statement_id)
        )
    )

    if entered_products != total_products:
        st.error(
            f"Statement incomplete: {entered_products} of {total_products} products entered"
        )
        st.stop()

    if st.button("✅ Final Submit Statement", type="primary"):

        # 1️⃣ Mark statement as final + release edit lock
        safe_exec(
            admin_supabase.table("statements")
            .update(
                {
                    "status": "final",
                    "final_submitted_at": datetime.utcnow().isoformat(),
                    "editing_by": None,
                    "editing_at": None,
                    "updated_at": datetime.utcnow().isoformat()
                }
            )
            .eq("id", st.session_state.statement_id)
        )

        # 🧾 Audit log — statement submitted (non-blocking)
        stmt_row = supabase.table("statements") \
            .select("stockist_id, year, month") \
            .eq("id", st.session_state.statement_id) \
            .limit(1) \
            .execute().data

        if stmt_row:
            stockist_row = supabase.table("stockists") \
            .select("name") \
            .eq("id", stmt_row[0]["stockist_id"]) \
            .limit(1) \
            .execute().data

        stockist_name = stockist_row[0]["name"] if stockist_row else "Unknown Stockist"

        log_audit(
            action="statement_submitted",
            target_type="statement",
            target_id=st.session_state.statement_id,
            performed_by=user_id,
            message=(
                f"Statement submitted for stockist "
                f"{stockist_name} "
                f"({stmt_row[0]['month']:02d}/{stmt_row[0]['year']})"
            ),
            metadata={
                "stockist_id": stmt_row[0]["stockist_id"],
                "stockist_name": stockist_name,
                "year": stmt_row[0]["year"],
                "month": stmt_row[0]["month"]
            }
        )

        # 2️⃣ Generate monthly summary (FINAL statements only)
        safe_exec(
            admin_supabase.rpc(
                "populate_monthly_summary",
                {"p_statement_id": st.session_state.statement_id}
            )
        )

        # 3️⃣ Show success & allow safe return to dashboard
        st.success("✅ Statement submitted successfully")

        if st.button("⬅ Back to Dashboard"):

            for k in [
                "statement_id",
                "product_index",
                "statement_year",
                "statement_month",
                "selected_stockist_id",
                "engine_stage"
            ]:
                st.session_state.pop(k, None)

            st.rerun()



# ======================================================
# ADMIN PANEL — NAVIGATION ONLY
# ======================================================
if role == "admin":

    st.title("Admin Dashboard")
    section = st.session_state.get("admin_section")

    if not section:
        st.info("Select an admin action from the sidebar")
        st.stop()

        
    

   
    # --------------------------------------------------
    # STATEMENTS
    # --------------------------------------------------
    if section == "Statements":

        st.subheader("📄 Statement Control Panel")

        rows = safe_exec(
            admin_supabase.table("statements")
            .select("""
                id, year, month, status, locked,
                editing_by, updated_at,
                stockists(name),
                users(username)
            """)
            .order("updated_at", desc=True)
        )

        if not rows:
            st.info("No statements available")
            st.stop()

        stmt = st.selectbox(
            "Select Statement",
            rows,
            format_func=lambda x: (
                f"{x['stockists']['name']} | "
                f"{x['month']}/{x['year']} | "
                f"{x['users']['username']} | "
                f"{'LOCKED' if x['locked'] else x['status'].upper()}"
            )
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("👁 View"):
                st.session_state.statement_id = stmt["id"]
                st.session_state.engine_stage = "view"
                st.rerun()

        with col2:
            
            if stmt["status"] == "final" and not stmt["locked"]:
                if st.button("🔒 Lock"):
                    safe_exec(
                        admin_supabase.table("statements")
                        .update({
-                           "locked": True,
-                           "status": "locked",
+                           "locked": True,
                            "locked_at": datetime.utcnow().isoformat(),
                            "locked_by": user_id
                        })
                        .eq("id", stmt["id"])
                    )
                    st.success("Statement locked")
                    st.rerun()

         with col3:
             if stmt["locked"]:
                 if st.button("🔓 Unlock"):
                     safe_exec(
                         admin_supabase.table("statements")
                         .update({
-                            "locked": False,
-                            "status": "final",
+                            "locked": False,
                             "locked_at": None,
                             "locked_by": None
                         })
                         .eq("id", stmt["id"])
                 )
                 st.success("Statement unlocked")
                 st.rerun()


        with col4:
            if st.button("🗑 Delete"):

                # 1️⃣ Delete statement products
                safe_exec(
                    admin_supabase.table("statement_products")
                    .delete()
                    .eq("statement_id", stmt["id"])
                )

                # 2️⃣ Delete statement
                safe_exec(
                    admin_supabase.table("statements")
                    .delete()
                    .eq("id", stmt["id"])
                )

                # 3️⃣ Audit log (human + developer friendly, non-blocking)
                log_audit(
                    action="delete_statement",
                    target_type="statement",
                    target_id=stmt["id"],
                    performed_by=user_id,
                    message=(
                        f"Admin deleted statement for "
                        f"{stmt['stockists']['name']} "
                        f"({stmt['month']:02d}/{stmt['year']})"
                    ),
                    metadata={
                        "stockist_id": stmt["stockist_id"],
                        "stockist_name": stmt["stockists"]["name"],
                        "month": stmt["month"],
                        "year": stmt["year"],
                        "status_before_delete": stmt["status"]
                    }
                )

                st.success("Statement permanently deleted")
                st.rerun()

    

    # --------------------------------------------------
    # USERS (EDIT + ASSIGN STOCKISTS)
    # --------------------------------------------------
    elif section == "Users":
        st.subheader("👤 Edit User & Assign Stockists")

        users = supabase.table("users") \
            .select("id, username, role, is_active") \
            .order("username") \
            .execute().data

        user = st.selectbox("Select User", users, format_func=lambda x: x["username"])

        is_active = st.checkbox("Active", value=user["is_active"])

        all_stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data

        assigned = supabase.table("user_stockists") \
            .select("stockist_id") \
            .eq("user_id", user["id"]) \
            .execute().data

        assigned_ids = [a["stockist_id"] for a in assigned]

        selected_stockists = st.multiselect(
            "Assigned Stockists",
            all_stockists,
            default=[s for s in all_stockists if s["id"] in assigned_ids],
            format_func=lambda x: x["name"]
        )

        if st.button("Save Changes"):
            supabase.table("users").update({
                "is_active": is_active,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user["id"]).execute()

            supabase.table("user_stockists").delete() \
                .eq("user_id", user["id"]).execute()

            for s in selected_stockists:
                supabase.table("user_stockists").insert({
                    "user_id": user["id"],
                    "stockist_id": s["id"]
                }).execute()

            # Audit log (human + developer friendly, non-blocking)
            log_audit(
                action="update_user",
                target_type="user",
                target_id=user["id"],
                performed_by=user_id,
                message=(
                    f"User '{user['username']}' updated "
                    f"(active={is_active}, "
                    f"stockists={', '.join(s['name'] for s in selected_stockists) or 'none'})"
                ),
                metadata={
                    "is_active": is_active,
                    "assigned_stockists": [s["name"] for s in selected_stockists]
                }
            )


            st.success("User updated successfully")

    # --------------------------------------------------
    # CREATE USER
    # --------------------------------------------------
    elif section == "Create User":
        st.subheader("➕ Create User")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Create User"):
            email = f"{username}@internal.local"

            auth_user = admin_supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True
            })

            supabase.table("users").insert({
                "id": auth_user.user.id,
                "username": username,
                "role": "user",
                "is_active": True
            }).execute()

            st.success("User created successfully")

    # --------------------------------------------------
    # STOCKISTS
    # --------------------------------------------------
    elif section == "Stockists":

        st.subheader("🏪 Stockists")

        # ===============================
        # ➕ ADD STOCKIST
        # ===============================
        st.markdown("### ➕ Add Stockist")

        name = st.text_input("Stockist Name *")
        location = st.text_input("Location")
        phone = st.text_input("Phone Number", value="9433245464")
        payment_terms = st.number_input(
        "Payment Terms (Days)",
        min_value=0,
        step=1
        )

        authorization_status = st.radio(
            "Authorization Status",
            ["AUTHORIZED", "NONAUTHORIZED"],
            horizontal=True
        )

        if st.button("Add Stockist"):
            if not name.strip():
                st.error("Stockist name is required")
                st.stop()

            supabase.table("stockists").insert({
                "name": name.strip(),
                "location": location.strip() or None,
                "phone": phone.strip() or "9433245464",
                "payment_terms": payment_terms or None,
                "authorization_status": authorization_status,
                "created_by": user_id
            }).execute()

            # Audit log (human + developer friendly, non-blocking)
            log_audit(
                action="create_stockist",
                target_type="stockist",
                target_id=None,  # created ID not needed for readability
                performed_by=user_id,
                message=f"Stockist '{name.strip()}' created",
                metadata={
                    "name": name.strip(),
                    "location": location.strip() or None,
                    "phone": phone.strip() or "9433245464",
                    "payment_terms": payment_terms or None,
                    "authorization_status": authorization_status
                }
            )


            st.cache_data.clear()
            st.success("Stockist added successfully")
            st.session_state["admin_section"] = "Statements"
            st.rerun()

        st.divider()

        # ===============================
        # ✏️ EDIT STOCKIST
        # ===============================
        st.markdown("### ✏️ Edit Stockist")

        stockists = load_stockists_cached()

        if not stockists:
            st.info("No stockists available")
            st.stop()

        stockist = st.selectbox(
            "Select Stockist",
            stockists,
            format_func=lambda x: x["name"]
        )

        edit_name = st.text_input(
            "Edit Name",
            value=stockist["name"]
        )

        edit_location = st.text_input(
            "Edit Location",
            value=stockist.get("location") or ""
        )

        edit_phone = st.text_input(
            "Edit Phone",
            value=stockist.get("phone") or "9433245464"
        )

        edit_payment_terms = st.number_input(
            "Edit Payment Terms (Days)",
            min_value=0,
            step=1,
            value=stockist.get("payment_terms") or 0
        )

        edit_authorization_status = st.radio(
            "Authorization Status",
            ["AUTHORIZED", "NONAUTHORIZED"],
            index=0 if stockist.get("authorization_status", "AUTHORIZED") == "AUTHORIZED" else 1,
            horizontal=True,
            key=f"edit_auth_status_{stockist['id']}"
        )

        if st.button("Save Changes"):
            if not edit_name.strip():
                st.error("Stockist name cannot be empty")
                st.stop()

            supabase.table("stockists").update({
                "name": edit_name.strip(),
                "location": edit_location.strip() or None,
                "phone": edit_phone.strip() or "9433245464",
                "payment_terms": edit_payment_terms or None,
                "authorization_status": edit_authorization_status
            }).eq("id", stockist["id"]).execute()

            supabase.table("audit_logs").insert({
                "action": "update_stockist",
                "target_type": "stockist",
                "target_id": stockist["id"],
                "performed_by": user_id,
                "metadata": {
                    "name": edit_name,
                    "location": edit_location,
                    "phone": edit_phone,
                    "payment_terms": edit_payment_terms,
                    "authorization_status": edit_authorization_status
                }
            }).execute()

            st.cache_data.clear()
            st.success("Stockist updated successfully")
            st.session_state["admin_section"] = "Statements"
            st.rerun()

        st.divider()

        # ===============================
        # 🗑 DELETE STOCKIST
        # ===============================
        st.markdown("### 🗑 Delete Stockist")

        if st.button("Delete Stockist"):
            used_in_statements = supabase.table("statements") \
                .select("id") \
                .eq("stockist_id", stockist["id"]) \
                .limit(1) \
                .execute().data

            used_in_users = supabase.table("user_stockists") \
                .select("user_id") \
                .eq("stockist_id", stockist["id"]) \
                .limit(1) \
                .execute().data

            if used_in_statements:
                st.error("❌ Stockist is used in statements — cannot delete")

            elif used_in_users:
                st.error("❌ Stockist is assigned to users — unassign users first")

            else:
                supabase.table("stockists") \
                    .delete() \
                    .eq("id", stockist["id"]) \
                    .execute()

                supabase.table("audit_logs").insert({
                    "action": "delete_stockist",
                    "target_type": "stockist",
                    "target_id": stockist["id"],
                    "performed_by": user_id,
                    "metadata": {
                        "name": stockist["name"]
                    }
                }).execute()

                st.cache_data.clear()
                st.success("✅ Stockist deleted successfully")
                st.session_state["admin_section"] = "Statements"
                st.rerun()



    # --------------------------------------------------
    # PRODUCTS CRUD
    # --------------------------------------------------
    elif section == "Products":
        st.subheader("📦 Products")

        name = st.text_input("Product Name")

        peak = st.multiselect("Peak Months", list(range(1, 13)))
        high = st.multiselect("High Months", list(range(1, 13)))
        low = st.multiselect("Low Months", list(range(1, 13)))
        lowest = st.multiselect("Lowest Months", list(range(1, 13)))

        if st.button("Add Product"):
            supabase.table("products").insert({
            "name": name.strip(),
            "peak_months": peak,
            "high_months": high,
            "low_months": low,
            "lowest_months": lowest
            }).execute()

            st.cache_data.clear()   # 🔄 CLEAR PRODUCT CACHE
            st.success("Product added")
            st.rerun()

        st.divider()

        products = load_products_cached()


        product = st.selectbox("Select Product", products, format_func=lambda x: x["name"])
        edit_name = st.text_input("Edit Name", value=product["name"])

        if st.button("Update Product"):
            supabase.table("products").update({
                "name": edit_name
                }).eq("id", product["id"]).execute()

            st.cache_data.clear()   # 🔄 CLEAR PRODUCT CACHE
            st.success("Product updated")
            st.rerun()


        if st.button("Delete Product"):
            used = supabase.table("statement_products") \
                .select("id") \
                .eq("product_id", product["id"]) \
                .limit(1) \
                .execute().data

            if used:
                st.error("Product used in statements")
            else:
                supabase.table("products").delete() \
                    .eq("id", product["id"]) \
                    .execute()

                st.cache_data.clear()   # 🔄 CLEAR CACHED PRODUCTS
                st.success("Product deleted")
                st.rerun()

    # --------------------------------------------------
    # RESET PASSWORD
    # --------------------------------------------------
    elif section == "Reset User Password":

        st.subheader("🔐 Reset User Password")

        users = supabase.table("users") \
            .select("id, username") \
            .order("username") \
            .execute().data

        u = st.selectbox("User", users, format_func=lambda x: x["username"])
        pwd = st.text_input("New Password", type="password")

        if st.button("Reset Password"):

            if not pwd.strip():
                st.error("Password cannot be empty")
                st.stop()

            if len(pwd) < 8:
                st.error("❌ Password must be at least 8 characters long")
                st.stop()

            try:
                admin_supabase.auth.admin.update_user_by_id(
                    u["id"],
                    {"password": pwd}
                )

                log_audit(
                    action="reset_user_password",
                    target_type="user",
                    target_id=u["id"],
                    performed_by=user_id,
                    message=f"Password reset for user '{u['username']}'",
                    metadata={}
                )

                st.success("✅ Password reset successfully")

            except Exception as e:
                st.error("❌ Password rejected by security policy")
                st.exception(e)




        

    # --------------------------------------------------
    # AUDIT LOGS
    # --------------------------------------------------
    elif section == "Audit Logs":
        st.subheader("📜 Audit Logs")

        # --------------------------------------------------
        # FILTERS
        # --------------------------------------------------
        f1, f2, f3 = st.columns(3)

        with f1:
            actions = (
                supabase.table("audit_logs")
                .select("action")
                .execute()
                .data
            )
            action_options = sorted(set(a["action"] for a in actions if a["action"]))
            selected_actions = st.multiselect(
                "Action",
                action_options,
                default=action_options
            )

        with f2:
            users = supabase.table("users") \
                .select("id, username") \
                .order("username") \
                .execute().data

            user_map = {u["id"]: u["username"] for u in users}
            selected_users = st.multiselect(
                "Performed By",
                users,
                format_func=lambda x: x["username"]
            )
            selected_user_ids = [u["id"] for u in selected_users]

        with f3:
            days = st.selectbox(
                "Time Range",
                [1, 3, 7, 30, 90, 365],
                index=3
            )

        # --------------------------------------------------
        # FETCH LOGS
        # --------------------------------------------------
        query = supabase.table("audit_logs") \
            .select("*") \
            .gte("created_at", (datetime.utcnow() - timedelta(days=days)).isoformat()) \
            .order("created_at", desc=True)

        if selected_actions:
            query = query.in_("action", selected_actions)

        if selected_user_ids:
            query = query.in_("performed_by", selected_user_ids)

        logs = query.execute().data

        if not logs:
            st.info("No audit logs found for selected filters")
            st.stop()

        # --------------------------------------------------
        # DISPLAY
        # --------------------------------------------------
        for log in logs:
            with st.expander(
                f"🕒 {log['created_at']} — {log['action']}",
                expanded=False
            ):
                st.markdown(f"**Message:** {log.get('message', '—')}")
                st.markdown(
                    f"**Performed By:** {user_map.get(log['performed_by'], 'Unknown')}"
                )
                st.markdown(f"**Target Type:** {log.get('target_type')}")
                st.markdown(f"**Target ID:** `{log.get('target_id')}`")

                if log.get("metadata"):
                    st.markdown("**Metadata:**")
                    st.json(log["metadata"])


    # --------------------------------------------------
    # LOCK / UNLOCK STATEMENTS
    # --------------------------------------------------
    elif section == "Lock / Unlock Statements":

        stmts = supabase.table("statements").select("*").execute().data

        if not stmts:
            st.info("No statements available")
            st.stop()

        s = st.selectbox(
            "Statement",
            stmts,
            format_func=lambda x: f"{x['year']}-{x['month']} | {x['status']}"
        )

        if not s:
            st.stop()

        if st.button("Lock", key="lock_statement_btn"):
            supabase.table("statements").update({
                "status": "locked",
                "locked_at": datetime.utcnow().isoformat(),
                "locked_by": user_id
            }).eq("id", s["id"]).execute()

            st.success("Statement locked")
            st.rerun()

        if st.button("Unlock", key="unlock_statement_btn"):
            supabase.table("statements").update({
                "status": "draft",
                "locked_at": None,
                "locked_by": None
            }).eq("id", s["id"]).execute()

            st.success("Statement unlocked")
            st.rerun()


    # --------------------------------------------------
    # ANALYTICS
    # --------------------------------------------------
    elif section == "Analytics":
        st.subheader("📊 Monthly Analytics")

        years = sorted(
            set(
                r["year"]
                for r in supabase.table("monthly_summary")
                .select("year")
                .execute().data
            )
        )

        if not years:
            st.info("No data available")
            st.stop()

        year = st.selectbox("Year", years)
        month = st.selectbox("Month", list(range(1, 13)))

        stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data

        stockist = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])

        rows = supabase.table("monthly_summary") \
            .select("total_issue, total_closing, total_order, products(name)") \
            .eq("year", year) \
            .eq("month", month) \
            .eq("stockist_id", stockist["id"]) \
            .execute().data

        if rows:
            df = pd.DataFrame([
                {
                    "Product": r["products"]["name"],
                    "Issue": r["total_issue"],
                    "Closing": r["total_closing"],
                    "Order": r["total_order"]
                }
                for r in rows
            ])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No data for selected period")
# ======================================================
# ======================================================
# REPORTS & MATRICES
# ======================================================
if st.session_state.get("engine_stage") == "reports":

    st.title("📊 Reports & Matrices")

    # --------------------------------------------------
    # COMMON FILTERS
    # --------------------------------------------------
    col1, col2, col3 = st.columns(3)

    with col1:
        if role == "admin":
            users = supabase.table("users").select("id, username").execute().data
            selected_users = st.multiselect(
                "Users",
                users,
                default=users,
                format_func=lambda x: x["username"]
            )
            user_ids = [u["id"] for u in selected_users]
        else:
            user_ids = [user_id]
            st.text_input("User", value="You", disabled=True)

    with col2:
        year_from = st.selectbox("Year From", list(range(2020, date.today().year + 1)))
        month_from = st.selectbox("Month From", list(range(1, 13)))

    with col3:
        year_to = st.selectbox("Year To", list(range(2020, date.today().year + 1)))
        month_to = st.selectbox("Month To", list(range(1, 13)))

    # --------------------------------------------------
    # STOCKIST FILTER
    # --------------------------------------------------
    if role == "admin":
        stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data
    else:
        raw = supabase.table("user_stockists") \
            .select("stockist_id, stockists(name)") \
            .eq("user_id", user_id) \
            .execute().data
        stockists = [{"id": r["stockist_id"], "name": r["stockists"]["name"]} for r in raw]

    selected_stockists = st.multiselect(
        "Stockists",
        stockists,
        default=stockists,
        format_func=lambda x: x["name"]
    )

    stockist_ids = [s["id"] for s in selected_stockists]

    # --------------------------------------------------
    # FETCH MONTHLY SUMMARY
    # --------------------------------------------------
    summary_rows = safe_exec(
        admin_supabase.table("monthly_summary")
        .select("""
            year,
            month,
            total_issue,
            total_closing,
            total_order,
            products(name),
            stockist_id
        """)
        .in_("stockist_id", stockist_ids)
    )

    if not summary_rows:
        st.info("No data for selected filters")

    else:
        # --------------------------------------------------
        # NORMALIZE DATA
        # --------------------------------------------------
        df = pd.DataFrame([
            {
                "Product": r["products"]["name"],
                "Year-Month": f"{r['year']}-{r['month']:02d}",
                "Issue": r["total_issue"],
                "Closing": r["total_closing"],
                "Order": r["total_order"]
            }
            for r in summary_rows
        ])

        # --------------------------------------------------
        # APPLY DRILLDOWN FILTER
        # --------------------------------------------------
        if "drilldown_product" not in st.session_state:
            st.session_state.drilldown_product = None

        if st.session_state.drilldown_product:
            df = df[df["Product"] == st.session_state.drilldown_product]

        # ==================================================
        # 🚨 ALERT BANNERS
        # ==================================================
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

        # --------------------------------------------------
        # DRILLDOWN CONTEXT
        # --------------------------------------------------
        if st.session_state.drilldown_product:
            st.info(
                f"🔍 Viewing detailed insights for "
                f"**{st.session_state.drilldown_product}**"
            )
            if st.button("⬅️ Back to All Products"):
                st.session_state.drilldown_product = None
                st.rerun()

        # ==================================================
        # MATRICES
        # ==================================================
        st.subheader("📦 Matrix 1 — Product-wise Sales (Issue)")
        st.dataframe(
            df.pivot_table(
                index="Product",
                columns="Year-Month",
                values="Issue",
                fill_value=0
            ),
            use_container_width=True
        )

        st.subheader("🧾 Matrix 2 — Product-wise Order")
        st.dataframe(
            df.pivot_table(
                index="Product",
                columns="Year-Month",
                values="Order",
                fill_value=0
            ),
            use_container_width=True
        )

        st.subheader("📊 Matrix 3 — Product-wise Closing")
        st.dataframe(
            df.pivot_table(
                index="Product",
                columns="Year-Month",
                values="Closing",
                fill_value=0
            ),
            use_container_width=True
        )

        st.subheader("📦📊 Matrix 4 — Issue & Closing")
        st.dataframe(
            df.melt(
                id_vars=["Product", "Year-Month"],
                value_vars=["Issue", "Closing"]
            ).pivot_table(
                index="Product",
                columns=["Year-Month", "variable"],
                values="value",
                fill_value=0
            ),
            use_container_width=True
        )

    # ==================================================
    # 📈 TREND CHARTS — LAST 6 MONTHS
    # ==================================================
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
            default_index = trend_products.index(
                st.session_state.drilldown_product
            )

        trend_product = st.selectbox(
            "Select Product for Trend",
            trend_products,
            index=default_index
        )

        chart_df = (
            df_trend[df_trend["Product"] == trend_product]
            .sort_values("Year-Month")
            .set_index("Year-Month")[["Issue", "Closing"]]
        )

        st.line_chart(chart_df)
    # ==================================================
    # 🔮 FORECAST — NEXT 3 MONTHS (SEASONAL LOGIC)
    # ==================================================
    st.subheader("🔮 Forecast — Next 3 Months")

    products_master = [
        p for p in load_products_cached()
        if "peak_months" in p
    ]

    forecast_rows = []

    for p in products_master:
        product_name = p["name"]
        df_p = df[df["Product"] == product_name]

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

            forecast_rows.append({
                "Product": product_name,
                "Forecast Month": f"{fy}-{fm:02d}",
                "Forecast Issue": round(last_issue * factor, 2)
            })

            fm += 1
            if fm == 13:
                fm = 1
                fy += 1

    if forecast_rows:
        forecast_df = pd.DataFrame(forecast_rows)

        st.dataframe(
            forecast_df.pivot_table(
                index="Product",
                columns="Forecast Month",
                values="Forecast Issue",
                fill_value=0
            ),
            use_container_width=True
        )
    else:
        st.info("Forecast not available for selected filters")

    # ==================================================
    # KPI — MONTH ON MONTH
    # ==================================================
    st.subheader("📊 KPI — Month-on-Month")

    kpi_df = df.groupby("Year-Month", as_index=False)["Issue"].sum().sort_values("Year-Month").tail(2)

    if len(kpi_df) == 2:
        cur, prev = kpi_df.iloc[1], kpi_df.iloc[0]
        mom = cur["Issue"] - prev["Issue"]
        pct = (mom / prev["Issue"] * 100) if prev["Issue"] else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Current Issue", round(cur["Issue"], 2))
        c2.metric("MoM Change", round(mom, 2), round(mom, 2))
        c3.metric("Growth %", f"{round(pct, 2)}%", f"{round(pct, 2)}%")
    else:
        st.info("Not enough data for KPI")

    # ==================================================
    # PRODUCT KPI CARDS
    # ==================================================
    st.subheader("📊 Product-level KPI Cards")

    product_list = sorted(df["Product"].unique())
    selected_product = st.selectbox("Select Product", product_list)

    df_p = df[df["Product"] == selected_product].sort_values("Year-Month")

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
