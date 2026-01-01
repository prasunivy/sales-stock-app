import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

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
for k in ["auth_user", "role"]:
    if k not in st.session_state:
        st.session_state[k] = None

# ======================================================
# USERNAME → INTERNAL EMAIL
# ======================================================
def username_to_email(username: str):
    res = supabase.table("users") \
        .select("id, is_active") \
        .eq("username", username) \
        .execute()

    if not res.data:
        return None

    if not res.data[0].get("is_active", True):
        raise Exception("Account disabled")

    return f"{username}@internal.local"

# ======================================================
# AUTH
# ======================================================
def login(username, password):
    email = username_to_email(username)
    if not email:
        raise Exception("Invalid username")

    return supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

def load_profile(user_id):
    res = supabase.table("users").select("*").eq("id", user_id).execute()
    return res.data[0]

# ======================================================
# STATEMENT RESOLVER
# ======================================================
def resolve_statement(user_id, stockist_id, year, month):
    res = supabase.table("statements") \
        .select("*") \
        .eq("stockist_id", stockist_id) \
        .eq("year", year) \
        .eq("month", month) \
        .execute()

    if not res.data:
        return {"mode": "create", "statement": None}

    stmt = res.data[0]

    if stmt["status"] == "final":
        return {"mode": "view", "statement": stmt}

    if stmt["status"] == "locked":
        return {"mode": "locked", "statement": stmt}

    return {"mode": "edit", "statement": stmt}

# ======================================================
# LOGIN UI
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
if role == "user":

    st.title("📊 Sales & Stock Statement")

    col1, col2, col3 = st.columns(3)
    with col1:
        create_clicked = st.button("➕ Create", use_container_width=True)
    with col2:
        edit_clicked = st.button("✏️ Edit", use_container_width=True)
    with col3:
        view_clicked = st.button("👁 View", use_container_width=True)

    st.divider()

    stockists = supabase.table("user_stockists") \
        .select("stockist_id, stockists(name)") \
        .eq("user_id", user_id) \
        .execute().data

    if not stockists:
        st.warning("No stockists allocated")
        st.stop()

    selected_stockist = st.selectbox(
        "Stockist",
        stockists,
        format_func=lambda x: x["stockists"]["name"]
    )

    current_year = datetime.now().year
    current_month = datetime.now().month

    year = st.selectbox("Year", [current_year - 1, current_year])
    month = st.selectbox("Month", list(range(1, current_month + 1)))

    action = None
    if create_clicked:
        action = "create"
    elif edit_clicked:
        action = "edit"
    elif view_clicked:
        action = "view"

    if action:
        result = resolve_statement(
            user_id,
            selected_stockist["stockist_id"],
            year,
            month
        )

        if action == "create" and result["mode"] in ("create", "edit"):
            if result["mode"] == "create":
                stmt = supabase.table("statements").insert({
                    "user_id": user_id,
                    "stockist_id": selected_stockist["stockist_id"],
                    "year": year,
                    "month": month,
                    "status": "draft",
                    "current_product_index": 0
                }).execute().data[0]
            else:
                stmt = result["statement"]

            st.session_state["statement_id"] = stmt["id"]
            st.session_state["product_index"] = stmt["current_product_index"] or 0
            st.session_state["engine_stage"] = "edit"
            st.rerun()

        elif result["mode"] == "locked":
            st.error("Statement already locked.")
            st.stop()

        elif result["mode"] == "view":
            st.warning("Statement already finalized. Use View.")
            st.stop()

# ======================================================
# PRODUCT ENGINE
# ======================================================
if role == "user" and "statement_id" in st.session_state:

    statement_id = st.session_state["statement_id"]
    product_index = st.session_state.get("product_index", 0)

    products = supabase.table("products") \
        .select("*") \
        .order("sort_order") \
        .execute().data

    if product_index >= len(products):
        st.session_state["engine_stage"] = "preview"
        st.rerun()

    product = products[product_index]

    st.subheader(
        f"Product {product_index + 1} of {len(products)} — {product['name']}"
    )

    existing = supabase.table("statement_products") \
        .select("*") \
        .eq("statement_id", statement_id) \
        .eq("product_id", product["id"]) \
        .execute().data

    row = existing[0] if existing else None

    opening = row["opening"] if row else 0
    purchase = row["purchase"] if row else 0
    issue = row["issue"] if row else 0
    closing = row["closing"] if row else opening
    order_qty = row["order_qty"] if row else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        opening = st.number_input("Opening", min_value=0.0, value=float(opening))
    with col2:
        purchase = st.number_input("Purchase", min_value=0.0, value=float(purchase))
    with col3:
        issue = st.number_input("Issue", min_value=0.0, value=float(issue))

    closing = st.number_input("Closing", min_value=0.0, value=float(closing))
    order_qty = st.number_input("Order Qty", min_value=0.0, value=float(order_qty))

    if st.button("💾 Save & Next"):
        supabase.table("statement_products").upsert({
            "statement_id": statement_id,
            "product_id": product["id"],
            "opening": opening,
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "order_qty": order_qty,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        st.session_state["product_index"] = product_index + 1
        st.rerun()

# ======================================================
# STEP 8 — PREVIEW
# ======================================================
if role == "user" and st.session_state.get("engine_stage") == "preview":

    preview_rows = supabase.table("statement_products") \
        .select("opening, purchase, issue, closing, order_qty, products(name)") \
        .eq("statement_id", st.session_state["statement_id"]) \
        .execute().data

    df = pd.DataFrame([
        {
            "Product": r["products"]["name"],
            "Opening": r["opening"],
            "Purchase": r["purchase"],
            "Issue": r["issue"],
            "Closing": r["closing"],
            "Order": r["order_qty"]
        }
        for r in preview_rows
    ])

    st.subheader("📋 Statement Preview")
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.subheader("✏️ Edit Product")

    product_names = [r["products"]["name"] for r in preview_rows]
    selected_name = st.selectbox("Select Product", product_names)

    if st.button("Edit Selected Product"):
        for idx, p in enumerate(products):
            if p["name"] == selected_name:
                st.session_state["product_index"] = idx
                st.session_state["engine_stage"] = "edit"
                st.rerun()

# ======================================================
# STEP 9 — FINAL SUBMIT
# ======================================================
if role == "user" and st.session_state.get("engine_stage") == "preview":

    st.divider()
    st.subheader("🚦 Final Submission")

    total_products = len(products)
    saved_products = len(preview_rows)

    if saved_products != total_products:
        st.error(f"Incomplete: {saved_products}/{total_products} products saved.")
        st.stop()

    if st.button("✅ Final Submit Statement"):
        supabase.table("statements").update({
            "status": "final",
            "final_submitted_at": datetime.utcnow().isoformat(),
            "current_product_index": None
        }).eq("id", st.session_state["statement_id"]).execute()

        st.session_state.clear()
        st.success("Statement finalized successfully.")
        st.rerun()

# ======================================================
# ADMIN PANEL
# ======================================================
if role == "admin":

    st.title("Admin Dashboard")

    section = st.radio(
        "Admin Section",
        [
            "Statements",
            "Audit Logs",
            "Analytics"
        ]
    )

    if section == "Statements":
        st.dataframe(pd.DataFrame(
            supabase.table("statements").select("*").execute().data
        ))

    elif section == "Audit Logs":
        logs = supabase.table("audit_logs") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute().data
        st.dataframe(pd.DataFrame(logs))

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
            st.warning("No data")
