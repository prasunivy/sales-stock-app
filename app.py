import streamlit as st
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Data Entry", layout="wide")

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
def login(u, p):
    res = supabase.table("users").select("*") \
        .eq("username", u.strip()).eq("password", p.strip()).execute().data
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
    if st.sidebar.button("Users"):
        st.session_state.nav = "Users"
    if st.sidebar.button("Products"):
        st.session_state.nav = "Products"
    if st.sidebar.button("Stockists"):
        st.session_state.nav = "Stockists"
    if st.sidebar.button("Allocate Stockists"):
        st.session_state.nav = "Allocate"
    if st.sidebar.button("View Statements"):
        st.session_state.nav = "View Statements"

if role == "user":
    if st.sidebar.button("New Statement"):
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
        st.write(f"{u['username']} ({u['role']})")

# =========================================================
# ================= ADMIN — PRODUCTS ======================
# =========================================================
if role == "admin" and st.session_state.nav == "Products":
    st.header("📦 Manage Products")

    pname = st.text_input("Product Name")
    if st.button("Add Product"):
        supabase.table("products").insert({"name": pname}).execute()
        st.success("Product added")

    for p in supabase.table("products").select("*").execute().data:
        st.write(p["name"])

# =========================================================
# ================= ADMIN — STOCKISTS =====================
# =========================================================
if role == "admin" and st.session_state.nav == "Stockists":
    st.header("🏪 Manage Stockists")

    sname = st.text_input("Stockist Name")
    if st.button("Add Stockist"):
        supabase.table("stockists").insert({"name": sname}).execute()
        st.success("Stockist added")

    for s in supabase.table("stockists").select("*").execute().data:
        st.write(s["name"])

# =========================================================
# ============ ADMIN — ALLOCATE STOCKISTS =================
# =========================================================
if role == "admin" and st.session_state.nav == "Allocate":
    st.header("🔗 Allocate Stockists")

    users = supabase.table("users").select("*").execute().data
    stockists = supabase.table("stockists").select("*").execute().data

    u = st.selectbox("User", users, format_func=lambda x: x["username"])
    s = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])

    if st.button("Allocate"):
        supabase.table("user_stockist_map").insert({
            "user_id": u["id"],
            "stockist_id": s["id"]
        }).execute()
        st.success("Allocated")

# =========================================================
# ================= USER — NEW STATEMENT ==================
# =========================================================
if role == "user" and st.session_state.nav == "New Statement":
    st.header("📝 New Sales & Stock Statement")

    stockists = supabase.table("user_stockist_map") \
        .select("stockist_id") \
        .eq("user_id", uid).execute().data

    stockist_ids = [s["stockist_id"] for s in stockists]
    stockist_map = {
        s["id"]: s["name"]
        for s in supabase.table("stockists").select("*").execute().data
        if s["id"] in stockist_ids
    }

    sel_stockist = st.selectbox(
        "Stockist",
        list(stockist_map.keys()),
        format_func=lambda x: stockist_map[x]
    )

    month = st.selectbox("Month", [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ])
    year = st.number_input("Year", value=datetime.now().year)

    if st.button("Create Statement"):
        res = supabase.table("sales_stock_statements").insert({
            "user_id": uid,
            "stockist_id": sel_stockist,
            "month": month,
            "year": year,
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
    prod = products[st.session_state.product_index]

    st.header(f"📦 {prod['name']}")

    opening = st.number_input("Opening", value=0)
    purchase = st.number_input("Purchase", value=0)
    issue = st.number_input("Issue", value=0)
    closing = st.number_input("Closing", value=0)

    diff = opening + purchase - issue - closing
    st.write(f"Difference: {diff}")

    if st.button("Save & Next"):
        supabase.table("sales_stock_items").insert({
            "statement_id": st.session_state.statement_id,
            "product_id": prod["id"],
            "opening": opening,
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "difference": diff
        }).execute()

        if st.session_state.product_index < len(products) - 1:
            st.session_state.product_index += 1
            st.rerun()
        else:
            supabase.table("sales_stock_statements") \
                .update({"status": "final"}) \
                .eq("id", st.session_state.statement_id).execute()
            st.success("Statement submitted")
            st.session_state.statement_id = None
