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
if st.sidebar.button("Logout"):
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

    if st.button("➕ Create / Resume"):
        res = admin_supabase.table("statements").upsert(
            {
                "user_id": user_id,
                "stockist_id": selected["stockist_id"],
                "year": year,
                "month": month,
                "status": "draft",
                "current_product_index": 0
            },
            on_conflict="stockist_id,year,month",
            returning="representation"
        ).execute()

        stmt = res.data[0]

        if stmt["status"] != "draft":
            st.error("Statement already locked or finalized")
            st.stop()

        st.session_state.statement_id = stmt["id"]
        st.session_state.product_index = stmt["current_product_index"]
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

    products = safe_exec(
        supabase.table("products")
        .select("*")
        .order("name")
    )

    if idx >= len(products):
        st.session_state.engine_stage = "preview"
        st.rerun()

    product = products[idx]

    st.subheader(f"Product {idx + 1} of {len(products)} — {product['name']}")

    # Fetch existing draft row (if any)
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
            st.metric(
                "📦 Suggested Order",
                live_row.get("order_qty", 0)
            )

        with g2:
            st.info(
                f"Issue Guidance: {live_row.get('issue_guidance', '—')}"
            )

        with g3:
            st.warning(
                f"Stock Guidance: {live_row.get('stock_guidance', '—')}"
            )
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
            .update({"current_product_index": st.session_state.product_index})
            .eq("id", sid)
        )

        st.rerun()

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

        # Build product_id → index mapping (ordered by product name)
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
    safe_exec(
        admin_supabase.table("statements")
        .update(
            {
                "status": "final",
                "final_submitted_at": datetime.utcnow().isoformat()
            }
        )
        .eq("id", st.session_state.statement_id)
    )

    st.session_state.engine_stage = "view"
    st.rerun()

# ======================================================
# READ-ONLY VIEW
# ======================================================
if (
    role == "user"
    and st.session_state.statement_id
    and st.session_state.engine_stage == "view"
):

    st.subheader("👁 Final Statement")

    rows = safe_exec(
        admin_supabase.table("statement_products")
        .select(
            "opening,purchase,issue,closing,difference,"
            "order_qty,issue_guidance,stock_guidance,"
            "products!statement_products_product_id_fkey(name)"
        )

        .eq("statement_id", st.session_state.statement_id)
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
                "Stock Guidance": r["stock_guidance"]
            }

            for r in rows
        ]
    )

    st.dataframe(df, use_container_width=True)

    st.download_button(
        "⬇️ Download CSV",
        df.to_csv(index=False),
        file_name="sales_stock_statement.csv",
        mime="text/csv"
    )


# ======================================================
# ADMIN PANEL — FULL CRUD RESTORED
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
        ]
    )

    # --------------------------------------------------
    # STATEMENTS
    # --------------------------------------------------
    if section == "Statements":
        st.dataframe(
            pd.DataFrame(
                supabase.table("statements").select("*").execute().data
            ),
            use_container_width=True
        )

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
    # STOCKISTS CRUD
    # --------------------------------------------------
    elif section == "Stockists":
        st.subheader("🏪 Stockists")

        name = st.text_input("New Stockist Name")

        if st.button("Add Stockist"):
            supabase.table("stockists").insert({
                "name": name,
                "created_by": user_id
            }).execute()

            supabase.table("audit_logs").insert({
                "action": "create_stockist",
                "target_type": "stockist",
                "performed_by": user_id,
                "metadata": {"name": name}
            }).execute()

            st.success("Stockist added")
            st.rerun()

        st.divider()

        stockists = supabase.table("stockists") \
            .select("*") \
            .order("name") \
            .execute().data

        stockist = st.selectbox("Select Stockist", stockists, format_func=lambda x: x["name"])
        edit_name = st.text_input("Edit Name", value=stockist["name"])

        if st.button("Save Changes"):
            supabase.table("stockists").update({
                "name": edit_name
            }).eq("id", stockist["id"]).execute()

            st.success("Stockist updated")
            st.rerun()

        if st.button("Delete Stockist"):
            used = supabase.table("statements") \
                .select("id") \
                .eq("stockist_id", stockist["id"]) \
                .limit(1) \
                .execute().data

            if used:
                st.error("Stockist in use — cannot delete")
            else:
                supabase.table("stockists") \
                    .delete() \
                    .eq("id", stockist["id"]) \
                    .execute()

                st.success("Stockist deleted")
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

            st.success("Product added")
            st.rerun()

        st.divider()

        products = supabase.table("products") \
            .select("*") \
            .order("name") \
            .execute().data

        product = st.selectbox("Select Product", products, format_func=lambda x: x["name"])
        edit_name = st.text_input("Edit Name", value=product["name"])

        if st.button("Update Product"):
            supabase.table("products").update({
                "name": edit_name
            }).eq("id", product["id"]).execute()

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

