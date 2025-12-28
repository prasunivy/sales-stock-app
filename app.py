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
    "Low": "🟡 LOW",
    "Neutral": "🟢 NEUTRAL"
}

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Exception Dashboard",
    "edit_statement_id": None,
    "refresh": 0
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
    if st.sidebar.button("📊 Exception Dashboard"):
        st.session_state.nav = "Exception Dashboard"
    if st.sidebar.button("🔐 Lock Control"):
        st.session_state.nav = "Lock Control"
    if st.sidebar.button("🤖 AI Seasonal Insights"):
        st.session_state.nav = "AI Seasonal Insights"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= AI SEASONAL INSIGHTS ==================
# =========================================================
if role == "admin" and st.session_state.nav == "AI Seasonal Insights":
    st.header("🤖 AI Seasonal Trend Insights")

    products = supabase.table("products").select("*").execute().data
    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data

    if not stmts:
        st.info("No statements available yet.")
        st.stop()

    months = sorted({f"{s['month']} {s['year']}" for s in stmts}, reverse=True)
    sel_month = st.selectbox("Select Month", months)

    month_name = sel_month.split()[0]

    shown = False

    for prod in products:
        pid = prod["id"]
        pname = prod["name"]

        peak = prod.get("peak_season_months") or []
        high = prod.get("high_season_months") or []
        low = prod.get("low_season_months") or []
        off = prod.get("off_season_months") or []

        if month_name in peak:
            season = "Peak"
        elif month_name in high:
            season = "High"
        elif month_name in low:
            season = "Low"
        elif month_name in off:
            season = "Off"
        else:
            season = "Neutral"

        related_items = []
        for i in items:
            if i["product_id"] != pid:
                continue
            stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
            if not stmt:
                continue
            if f"{stmt['month']} {stmt['year']}" == sel_month:
                related_items.append(i)

        if not related_items:
            continue

        shown = True
        total_issue = sum(i["issue"] for i in related_items)
        total_closing = sum(i["closing"] for i in related_items)

        if season == "Peak" and total_issue == 0:
            sev, msg = "High", "Underperforming in peak season"
        elif season == "Off" and total_closing > 0:
            sev, msg = "Medium", "Stock buildup outside season"
        elif season == "Off":
            sev, msg = "Low", "Seasonal slowdown is normal"
        else:
            sev, msg = "Neutral", "No abnormal seasonal behavior"

        with st.container(border=True):
            st.markdown(f"### {SEVERITY_BADGE[sev]} {pname}")
            st.write(f"**Month:** {sel_month}")
            st.write(f"**Season Context:** {season}")
            st.write(f"**Total Issue:** {total_issue}")
            st.write(f"**Total Closing:** {total_closing}")
            st.write(f"**Insight:** {msg}")

    if not shown:
        st.info("No product data found for the selected month.")

# =========================================================
# ================= PLACEHOLDER DASHBOARDS ================
# =========================================================
if role == "admin" and st.session_state.nav == "Exception Dashboard":
    st.info("Exception Dashboard (already implemented earlier)")

if role == "admin" and st.session_state.nav == "Lock Control":
    st.info("Lock Control (already implemented earlier)")

st.write("---")
st.write("© Ivy Pharmaceuticals")
