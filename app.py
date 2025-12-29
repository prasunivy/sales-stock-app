import streamlit as st
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SEVERITY = {
    "High": "🔴 HIGH",
    "Medium": "🟠 MEDIUM",
    "Low": "🟡 LOW"
}

MONTH_ORDER = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Home",
    "statement_id": None,
    "product_index": 0,
    "view_stmt_id": None,
    "edit_stmt_id": None,
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
st.title("Ivy Pharmaceuticals — Sales & Stock")

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
    if st.sidebar.button("📝 Data Entry"):
        st.session_state.nav = "Home"
    if st.sidebar.button("📊 Exception Dashboard"):
        st.session_state.nav = "Exceptions"
    if st.sidebar.button("🔐 Lock Control"):
        st.session_state.nav = "Lock"
    if st.sidebar.button("📈 Matrix Dashboards"):
        st.session_state.nav = "Matrix"
    if st.sidebar.button("🤖 AI Seasonal Insights"):
        st.session_state.nav = "AI"

if role == "user":
    if st.sidebar.button("📝 New Statement"):
        st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — MATRIX DASHBOARDS =============
# =========================================================
if role == "admin" and st.session_state.nav == "Matrix":
    st.header("📈 Matrix Dashboards")

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data
    products = supabase.table("products").select("*").execute().data

    # ---------------- MATRIX 1 ----------------
    st.subheader("📊 Matrix 1 — Month × Product")

    year_sel = st.selectbox(
        "Year",
        sorted({s["year"] for s in stmts}, reverse=True),
        key="m1_year"
    )

    month_sel = st.selectbox(
        "Month",
        MONTH_ORDER,
        key="m1_month"
    )

    matrix1 = []

    for p in products:
        p_items = []
        for i in items:
            stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
            if not stmt:
                continue
            if stmt["year"] == year_sel and stmt["month"] == month_sel and i["product_id"] == p["id"]:
                p_items.append(i)

        if not p_items:
            continue

        matrix1.append({
            "Product": p["name"],
            "Opening": sum(i["opening"] for i in p_items),
            "Purchase": sum(i["purchase"] for i in p_items),
            "Issue": sum(i["issue"] for i in p_items),
            "Closing": sum(i["closing"] for i in p_items),
            "Difference": sum(i["difference"] for i in p_items)
        })

    if matrix1:
        st.dataframe(matrix1, use_container_width=True)
    else:
        st.info("No data for selected month.")

    st.divider()

    # ---------------- MATRIX 2 ----------------
    st.subheader("📈 Matrix 2 — Product × Month")

    prod_sel = st.selectbox(
        "Product",
        products,
        format_func=lambda x: x["name"],
        key="m2_prod"
    )

    year_sel2 = st.selectbox(
        "Year",
        sorted({s["year"] for s in stmts}, reverse=True),
        key="m2_year"
    )

    matrix2 = []

    for m in MONTH_ORDER:
        m_items = []
        for i in items:
            stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
            if not stmt:
                continue
            if stmt["year"] == year_sel2 and stmt["month"] == m and i["product_id"] == prod_sel["id"]:
                m_items.append(i)

        if not m_items:
            continue

        matrix2.append({
            "Month": m,
            "Opening": sum(i["opening"] for i in m_items),
            "Purchase": sum(i["purchase"] for i in m_items),
            "Issue": sum(i["issue"] for i in m_items),
            "Closing": sum(i["closing"] for i in m_items),
            "Difference": sum(i["difference"] for i in m_items)
        })

    if matrix2:
        st.dataframe(matrix2, use_container_width=True)
    else:
        st.info("No data for selected product/year.")

st.write("---")
st.write("© Ivy Pharmaceuticals")
