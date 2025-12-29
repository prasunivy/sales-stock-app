import streamlit as st
from supabase import create_client
from datetime import datetime

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

MONTH_ORDER = [
    "April","May","June","July","August","September",
    "October","November","December","January","February","March"
]

# ======================================================
# SESSION STATE
# ======================================================
for k in [
    "logged_in", "user", "nav",
    "statement_id", "product_index"
]:
    st.session_state.setdefault(k, None)

# ======================================================
# HELPERS
# ======================================================
def safe_select(table, **filters):
    try:
        q = supabase.table(table).select("*")
        for k, v in filters.items():
            q = q.eq(k, v)
        return q.execute().data or []
    except Exception as e:
        st.error(f"{table} read error")
        return []

def safe_insert(table, payload):
    try:
        supabase.table(table).insert(payload).execute()
        return True
    except:
        st.error(f"{table} insert failed")
        return False

def login(username, password):
    res = safe_select(
        "users",
        username=username.strip(),
        password=password.strip()
    )
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.session_state.nav = "Users" if res[0]["role"] == "admin" else "My Statements"
        st.rerun()
    else:
        st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

# ======================================================
# LOGIN (FIXED)
# ======================================================
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login", use_container_width=True)

    if submit:
        login(u, p)

    st.stop()

user = st.session_state.user
role = user["role"]
uid = user["id"]

# ======================================================
# SIDEBAR NAVIGATION (STABLE)
# ======================================================
st.sidebar.title("Menu")

if role == "admin":
    if st.sidebar.button("Users"): st.session_state.nav = "Users"
    if st.sidebar.button("Products"): st.session_state.nav = "Products"
    if st.sidebar.button("Stockists"): st.session_state.nav = "Stockists"
    if st.sidebar.button("Allocate"): st.session_state.nav = "Allocate"

if role == "user":
    if st.sidebar.button("My Statements"): st.session_state.nav = "My Statements"
    if st.sidebar.button("New Statement"): st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# ======================================================
# ADMIN — USERS
# ======================================================
if role == "admin" and st.session_state.nav == "Users":
    st.header("👤 Users")

    with st.form("add_user"):
        uname = st.text_input("Username")
        pwd = st.text_input("Password")
        r = st.selectbox("Role", ["user", "admin"])
        if st.form_submit_button("Add User", use_container_width=True):
            safe_insert("users", {
                "username": uname,
                "password": pwd,
                "role": r
            })
            st.rerun()

    st.subheader("Existing Users")
    for u in safe_select("users"):
        st.write(f"{u.get('username')} ({u.get('role')})")

# ======================================================
# ADMIN — PRODUCTS
# ======================================================
if role == "admin" and st.session_state.nav == "Products":
    st.header("📦 Products")

    with st.form("add_product"):
        name = st.text_input("Product Name")
        peak = st.number_input("Peak", 0)
        high = st.number_input("High", 0)
        low = st.number_input("Low", 0)
        lowest = st.number_input("Lowest", 0)
        if st.form_submit_button("Add Product", use_container_width=True):
            safe_insert("products", {
                "name": name,
                "peak": peak,
                "high": high,
                "low": low,
                "lowest": lowest
            })
            st.rerun()

    st.subheader("Existing Products")
    for p in safe_select("products"):
        st.write(
            f"{p.get('name')} | "
            f"Peak:{p.get('peak',0)} "
            f"High:{p.get('high',0)} "
            f"Low:{p.get('low',0)} "
            f"Lowest:{p.get('lowest',0)}"
        )

# ======================================================
# ADMIN — STOCKISTS
# ======================================================
if role == "admin" and st.session_state.nav == "Stockists":
    st.header("🏪 Stockists")

    with st.form("add_stockist"):
        name = st.text_input("Stockist Name")
        if st.form_submit_button("Add Stockist", use_container_width=True):
            safe_insert("stockists", {"name": name})
            st.rerun()

    for s in safe_select("stockists"):
        st.write(s.get("name"))

# ======================================================
# ADMIN — ALLOCATE
# ======================================================
if role == "admin" and st.session_state.nav == "Allocate":
    st.header("🔗 Allocate Stockists")

    users = safe_select("users")
    stockists = safe_select("stockists")

    if not users or not stockists:
        st.warning("Users or stockists missing")
    else:
        with st.form("allocate"):
            u = st.selectbox("User", users, format_func=lambda x: x["username"])
            s = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])
            if st.form_submit_button("Allocate", use_container_width=True):
                safe_insert("user_stockist", {
                    "user_id": u["id"],
                    "stockist_id": s["id"]
                })
                st.success("Allocated")

# ======================================================
# USER — MY STATEMENTS
# ======================================================
if role == "user" and st.session_state.nav == "My Statements":
    st.header("📄 My Statements")

    stmts = safe_select("sales_stock_statements", user_id=uid)
    stockists = safe_select("stockists")
    smap = {s["id"]: s["name"] for s in stockists}

    if not stmts:
        st.info("No statements yet")

    for s in stmts:
        st.write(
            f"{s.get('month')} {s.get('year')} | "
            f"{smap.get(s.get('stockist_id'),'—')} | "
            f"{s.get('status')}"
        )

# ======================================================
# USER — NEW STATEMENT
# ======================================================
if role == "user" and st.session_state.nav == "New Statement":
    st.header("📝 New Statement")

    mappings = safe_select("user_stockist", user_id=uid)
    stockists = safe_select("stockists")
    stockists = [s for s in stockists if s["id"] in [m["stockist_id"] for m in mappings]]

    if not stockists:
        st.warning("No stockist allocated. Contact admin.")
    else:
        with st.form("create_statement"):
            stck = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])
            month = st.selectbox("Month", MONTH_ORDER)
            year = st.number_input("Year", value=datetime.now().year)
            if st.form_submit_button("Create Statement", use_container_width=True):
                ok = safe_insert("sales_stock_statements", {
                    "user_id": uid,
                    "stockist_id": stck["id"],
                    "month": month,
                    "year": int(year),
                    "status": "draft",
                    "locked": False
                })
                if ok:
                    st.success("Statement created")

st.write("---")
st.write("© Ivy Pharmaceuticals")
