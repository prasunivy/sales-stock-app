import streamlit as st
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock Entry",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Home",
    "statement_id": None,
    "product_index": 0
}.items():
    st.session_state.setdefault(k, v)

# ================= AUTH =================
def login(username, password):
    res = supabase.table("users") \
        .select("*") \
        .eq("username", username.strip()) \
        .eq("password", password.strip()) \
        .execute().data
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.rerun()
    st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

# ================= LOGIN =================
st.title("Ivy Pharmaceuticals — Sales & Stock Entry")

if not st.session_state.logged_in:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u, p)
    st.stop()

role = st.session_state.user["role"]
uid = st.session_state.user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role == "admin":
    if st.sidebar.button("👤 Users"):
        st.session_state.nav = "Users"
    if st.sidebar.button("📦 Products"):
        st.session_state.nav = "Products"
    if st.sidebar.button("🏪 Stockists"):
        st.session_state.nav = "Stockists"
    if st.sidebar.button("🔗 Allocate Stockists"):
        st.session_state.nav = "Allocate"
    if st.sidebar.button("📄 View Statements"):
        st.session_state.nav = "View Statements"

if role == "user":
    if st.sidebar.button("📝 New Statement"):
        st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — USERS =========================
# =========================================================
if role == "admin" and st.session_state.nav == "Users":
    st.header("👤 Manage Users")

    uname = st.text_input("Username")
    pwd = st.text_input("Password")
    role_sel = st.selectbox("Role", ["user", "admin"])

    if st.button("Add User"):
        supabase.table("users").insert({
            "username": uname,
            "password": pwd,
            "role": role_sel
        }).execute()
        st.success("User added")

    st.subheader("Existing Users")
    for u in supabase.table("users").select("*").execute().data:
        st.write(f"- {u['username']} ({u['role']})")

# =========================================================
# ================= ADMIN — PRODUCTS ======================
# =========================================================
if role == "admin" and st.session_state.nav == "Products":
    st.header("📦 Manage Products")

    pname = st.text_input("Product Name")
    if st.button("Add Product"):
        supabase.table("products").insert({"name": pname}).execute()
        st.success("Product added")

    st.subheader("Existing Products")
    for p in supabase.table("products").select("*").order("name").execute().data:
        st.write(f"- {p['name']}")

# =========================================================
# ================= ADMIN — STOCKISTS =====================
# =========================================================
if role == "admin" and st.session_state.nav == "Stockists":
    st.header("🏪 Manage Stockists")

    sname = st.text_input("Stockist Name")
    if st.button("Add Stockist"):
        supabase.table("stockists").insert({"name": sname}).execute()
        st.success("Stockist added")

    st.subheader("Existing Stockists")
    for s in supabase.table("stockists").select("*").order("name").execute().data:
        st.write(f"- {s['name']}")

# =========================================================
# ============ ADMIN — ALLOCATE STOCKISTS =================
# =========================================================
if role == "admin" and st.session_state.nav == "Allocate":
    st.header("🔗 Allocate Stockists to Users")

    users = supabase.table("users").select("*").execute().data
    stockists = supabase.table("stockists").select("*").execute().data

    sel_user = st.selectbox(
        "Select User",
        users,
        format_func=lambda x: x["username"]
    )
    sel_stockist = st.selectbox(
        "Select Stockist",
        stockists,
        format_func=lambda x: x["name"]
    )

    if st.button("Allocate"):
        supabase.table("user_stockist").insert({
            "user_id": sel_user["id"],
            "stockist_id": sel_stockist["id"]
        }).execute()
        st.success("Stockist allocated to user")

# =========================================================
# ================= USER — NEW STATEMENT ==================
# =========================================================
if role == "user" and st.session_state.nav == "New Statement":
    st.header("📝 New Sales & Stock Statement")

    mappings = supabase.table("user_stockist") \
        .select("stockist_id") \
        .eq("user_id", uid) \
        .execute().data

    if not mappings:
        st.warning("No stockist allocated. Contact admin.")
        st.stop()

    stockist_ids = [m["stockist_id"] for m in mappings]

    stockists = supabase.table("stockists") \
        .select("*") \
        .in_("id", stockist_ids) \
        .execute().data

    sel_stockist = st.selectbox(
        "Stockist",
        stockists,
        format_func=lambda x: x["name"]
    )

    month = st.selectbox(
        "Month",
        ["January","February","March","April","May","June",
         "July","August","September","October","November","December"]
    )
    year = st.number_input("Year", value=datetime.now().year)

    if st.button("Create Statement"):
        res = supabase.table("sales_stock_statements").insert({
            "user_id": uid,
            "stockist_id": sel_stockist["id"],
            "month": month,
            "year": int(year),
            "status": "draft",
            "locked": False
        }).execute()

        st.session_state.statement_id = res.data[0]["id"]
        st.session_state.product_index = 0
        st.rerun()

# =========================================================
# ================= PRODUCT ENTRY =========================
# =========================================================
if role == "user" and st.session_state.statement_id:
    products = supabase.table("products").select("*").order("name").execute().data

    if st.session_state.product_index >= len(products):
        st.success("All products entered. Statement submitted.")
        supabase.table("sales_stock_statements") \
            .update({"status": "final"}) \
            .eq("id", st.session_state.statement_id) \
            .execute()
        st.session_state.statement_id = None
        st.stop()

    prod = products[st.session_state.product_index]

    st.header(f"📦 {prod['name']}")

    opening = st.number_input("Opening", value=0, step=1)
    purchase = st.number_input("Purchase", value=0, step=1)
    issue = st.number_input("Issue", value=0, step=1)
    closing = st.number_input("Closing", value=0, step=1)

    difference = opening + purchase - issue - closing
    st.write(f"**Difference:** {difference}")

    if st.button("Save & Next"):
        supabase.table("sales_stock_items").insert({
            "statement_id": st.session_state.statement_id,
            "product_id": prod["id"],
            "opening": opening,
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "difference": difference
        }).execute()

        st.session_state.product_index += 1
        st.rerun()
