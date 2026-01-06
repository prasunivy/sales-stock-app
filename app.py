import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
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
    "engine_stage"
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
# LOGIN
# ======================================================
if not st.session_state.auth_user:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            auth = login(username, password)
            profile = load_profile(auth.user.id)
            st.session_state.auth_user = auth.user
            st.session_state.role = profile["role"]
            st.rerun()
        except Exception as e:
            st.error(str(e))

    st.stop()

# ======================================================
# SIDEBAR
# ======================================================
st.sidebar.title("Navigation")
if st.sidebar.button("📊 Reports"):
    st.session_state.engine_stage = "reports"
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


role = st.session_state.role
user_id = st.session_state.auth_user.id

# ======================================================
# USER LANDING
# ======================================================
if role == "user" and not st.session_state.statement_id:

    st.title("📊 Sales & Stock Statement")

    stockists = safe_exec(
        supabase.table("user_stockists")
        .select("stockist_id, stockists(name)")
        .eq("user_id", user_id)
    )

    selected = st.selectbox(
        "Stockist",
        stockists,
        format_func=lambda x: x["stockists"]["name"]
    )

    today = date.today()
    year = st.selectbox("Year", [today.year - 1, today.year])
    month = st.selectbox(
        "Month",
        list(range(1, today.month + 1)) if year == today.year else list(range(1, 13))
    )

    # 🔁 Detect existing draft for resume
    existing_draft = safe_exec(
        admin_supabase.table("statements")
        .select("id, current_product_index, editing_by, status, locked")
        .eq("user_id", user_id)
        .eq("stockist_id", selected["stockist_id"])
        .eq("year", year)
        .eq("month", month)
        .eq("status", "draft")
        .limit(1)
    )

    if existing_draft:
        draft = existing_draft[0]

        if draft["locked"]:
            st.warning("Draft exists but is locked by admin")
        else:
            st.info(
                f"📝 You have an unfinished draft for {month}/{year}. "
                f"Progress saved till product #{draft['current_product_index'] + 1}. "
                "You can safely resume from where you left off."
            )


            if st.button("▶ Resume Draft"):
                # 🚫 Block if another device editing
                if draft["editing_by"] and draft["editing_by"] != user_id:
                    st.error("Statement currently open on another device")
                    st.stop()

                # ✅ Acquire edit lock
                safe_exec(
                    admin_supabase.table("statements")
                    .update({
                        "editing_by": user_id,
                        "editing_at": datetime.utcnow().isoformat()
                    })
                    .eq("id", draft["id"])
                )

                st.session_state.statement_id = draft["id"]
                st.session_state.product_index = draft["current_product_index"] or 0
                st.session_state.statement_year = year
                st.session_state.statement_month = month
                st.session_state.selected_stockist_id = selected["stockist_id"]
                st.session_state.engine_stage = "edit"

                st.rerun()

    if st.button("➕ Create / Resume"):

        res = admin_supabase.table("statements").upsert(
            {
                "user_id": user_id,
                "stockist_id": selected["stockist_id"],
                "year": year,
                "month": month,
                "status": "draft",
                "engine_stage": "edit",
                "current_product_index": 0,
                "updated_at": datetime.utcnow().isoformat()
            },
            on_conflict="stockist_id,year,month",
            returning="representation"
        ).execute()

        stmt = res.data[0]

        # 🚫 Hard lock by admin
        if stmt["locked"] or stmt["status"] == "locked":
            st.error("Statement already locked by admin")
            st.stop()

        # 🚫 Single active editor rule
        if stmt["editing_by"] and stmt["editing_by"] != user_id:
            st.error("Statement currently open on another device")
            st.stop()

        # ✅ Acquire edit lock
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
        st.session_state.product_index = stmt["current_product_index"] or 0
        st.session_state.statement_year = year
        st.session_state.statement_month = month
        st.session_state.selected_stockist_id = selected["stockist_id"]
        st.session_state.engine_stage = "edit"

        st.rerun()

    

# ======================================================
# PRODUCT ENGINE
# ======================================================
if (
    role == "user"
    and st.session_state.statement_id
    and st.session_state.engine_stage == "edit"
):

    sid = st.session_state.statement_id
    idx = st.session_state.product_index

    products = load_products_cached()

    

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
        value=float(row.get("opening", last_closing)),
        key=f"opening_{sid}_{product['id']}"
    )

    st.caption(f"Last Month Issue: {last_issue}")

    purchase = st.number_input(
        "Purchase",
        value=float(row.get("purchase", 0)),
        key=f"purchase_{sid}_{product['id']}"
    )

    issue = st.number_input(
        "Issue",
        value=float(row.get("issue", 0)),
        key=f"issue_{sid}_{product['id']}"
    )

    calculated_closing = opening + purchase - issue

    closing = st.number_input(
        "Closing",
        value=float(row.get("closing", calculated_closing)),
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
                    "opening": opening,
                    "last_month_issue": last_issue,
                    "purchase": purchase,
                    "issue": issue,
                    "closing": closing,
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
# ======================================================
# PREVIEW & EDIT JUMP
# ======================================================
if (
    role == "user"
    and st.session_state.statement_id
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

    st.dataframe(df.drop(columns=["Product ID"]), use_container_width=True)

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

        # 2️⃣ Generate monthly summary (FINAL statements only)
        safe_exec(
            admin_supabase.rpc(
                "populate_monthly_summary",
                {"p_statement_id": st.session_state.statement_id}
            )
        )

        # 3️⃣ Move to read-only view
        st.session_state.engine_stage = "view"
        st.rerun()


# ======================================================
# ADMIN PANEL — NAVIGATION ONLY
# ======================================================
if role == "admin":

    st.title("Admin Dashboard")

   
    
    section = st.radio(
        "Admin Section",
        [
            "Statements",
            "Users",
            "Create User",
            "Stockists",
            "Products",
            "Reset User Password",
            "Audit Logs",
            "Lock / Unlock Statements",
            "Analytics"
        ],
        index=0
    )
    

   
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
                            "locked": True,
                            "status": "locked",
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
                            "locked": False,
                            "status": "final",
                            "locked_at": None,
                            "locked_by": None
                        })
                        .eq("id", stmt["id"])
                    )
                    st.success("Statement unlocked")
                    st.rerun()

        with col4:
            if st.button("🗑 Delete"):
                safe_exec(
                    admin_supabase.table("statement_products")
                    .delete()
                    .eq("statement_id", stmt["id"])
                )
                safe_exec(
                    admin_supabase.table("statements")
                    .delete()
                    .eq("id", stmt["id"])
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

            supabase.table("audit_logs").insert({
                "action": "update_user",
                "target_type": "user",
                "target_id": user["id"],
                "performed_by": user_id,
                "metadata": {
                    "is_active": is_active,
                    "stockists": [s["name"] for s in selected_stockists]
                }
            }).execute()

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

            supabase.table("audit_logs").insert({
                "action": "create_stockist",
                "target_type": "stockist",
                "performed_by": user_id,
                "metadata": {
                    "name": name,
                    "location": location,
                    "phone": phone,
                    "payment_terms": payment_terms,
                    "authorization_status": authorization_status
                }
            }).execute()

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
        users = supabase.table("users") \
            .select("id, username") \
            .execute().data

        u = st.selectbox("User", users, format_func=lambda x: x["username"])
        pwd = st.text_input("New Password", type="password")

        if st.button("Reset Password"):
            admin_supabase.auth.admin.update_user_by_id(
                u["id"],
                {"password": pwd}
            )
            st.success("Password reset successfully")

    # --------------------------------------------------
    # AUDIT LOGS
    # --------------------------------------------------
    elif section == "Audit Logs":
        logs = supabase.table("audit_logs") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute().data

        st.dataframe(pd.DataFrame(logs), use_container_width=True)

    # --------------------------------------------------
    # LOCK / UNLOCK STATEMENTS
    # --------------------------------------------------
    elif section == "Lock / Unlock Statements":
        stmts = supabase.table("statements").select("*").execute().data

        s = st.selectbox(
            "Statement",
            stmts,
            format_func=lambda x: f"{x['year']}-{x['month']} | {x['status']}"
        )

        if st.button("Lock"):
            supabase.table("statements").update({
                "status": "locked",
                "locked_at": datetime.utcnow().isoformat(),
                "locked_by": user_id
            }).eq("id", s["id"]).execute()

            st.success("Statement locked")

        if st.button("Unlock"):
            supabase.table("statements").update({
                "status": "draft"
            }).eq("id", s["id"]).execute()

            st.success("Statement unlocked")

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
        stockists = supabase.table("stockists").select("id, name").order("name").execute().data
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
        st.stop()

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
    # 🚨 ALERT BANNERS (CLICKABLE)
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
        st.info(f"🔍 Viewing detailed insights for **{st.session_state.drilldown_product}**")
        if st.button("⬅️ Back to All Products"):
            st.session_state.drilldown_product = None
            st.rerun()

    # ==================================================
    # MATRIX 1 — PRODUCT-WISE SALES
    # ==================================================
    st.subheader("📦 Matrix 1 — Product-wise Sales (Issue)")
    st.dataframe(
        df.pivot_table(index="Product", columns="Year-Month", values="Issue", fill_value=0),
        use_container_width=True
    )

    # ==================================================
    # MATRIX 2 — PRODUCT-WISE ORDER
    # ==================================================
    st.subheader("🧾 Matrix 2 — Product-wise Order")
    st.dataframe(
        df.pivot_table(index="Product", columns="Year-Month", values="Order", fill_value=0),
        use_container_width=True
    )

    # ==================================================
    # MATRIX 3 — PRODUCT-WISE CLOSING
    # ==================================================
    st.subheader("📊 Matrix 3 — Product-wise Closing")
    st.dataframe(
        df.pivot_table(index="Product", columns="Year-Month", values="Closing", fill_value=0),
        use_container_width=True
    )

    # ==================================================
    # MATRIX 4 — ISSUE + CLOSING
    # ==================================================
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
