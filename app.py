import streamlit as st
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SEVERITY_BADGE = {
    "High": "🔴 HIGH",
    "Medium": "🟠 MEDIUM",
    "Low": "🟡 LOW"
}

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Exception Dashboard",
    "edit_statement_id": None
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
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u, p)
    st.stop()

role = st.session_state.user["role"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")
if role == "admin":
    if st.sidebar.button("Exception Dashboard"):
        st.session_state.nav = "Exception Dashboard"
if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ============ EXCEPTION DASHBOARD ========================
# =========================================================
if role == "admin" and st.session_state.nav == "Exception Dashboard":
    st.header("🚨 Exception Dashboard")

    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}
    products = {p["id"]: p["name"] for p in supabase.table("products").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data

    # ---------- Build month list ----------
    months = sorted(
        {f"{s['month']} {s['year']}" for s in stmts},
        reverse=True
    )

    selected_month = st.selectbox(
        "Filter Product Exceptions by Month",
        ["All"] + months
    )

    st.subheader("📦 Product-level Exceptions")

    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        month_label = f"{stmt['month']} {stmt['year']}"
        if selected_month != "All" and month_label != selected_month:
            continue

        severity = None
        reason = None

        if i["difference"] != 0:
            severity = "High"
            reason = "Stock Mismatch"
        elif i["issue"] == 0 and i["closing"] > 0:
            severity = "Medium"
            reason = "Zero Issue, Stock Present"
        elif i["issue"] > 0 and i["closing"] >= 2 * i["issue"]:
            severity = "Low"
            reason = "Closing ≥ 2× Issue"

        if severity:
            with st.container(border=True):
                st.markdown(f"### {SEVERITY_BADGE[severity]}")
                st.write(f"**Product:** {products.get(i['product_id'], 'Unknown')}")
                st.write(f"**Stockist:** {stockists.get(stmt['stockist_id'], 'Unknown')}")
                st.write(f"**Month:** {month_label}")
                st.write(f"**Issue:** {i['issue']}")
                st.write(f"**Closing:** {i['closing']}")
                st.write(f"**Reason:** {reason}")

st.write("---")
st.write("© Ivy Pharmaceuticals")

