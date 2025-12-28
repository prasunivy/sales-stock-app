import streamlit as st
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "AI Seasonal Insights",
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
    if st.sidebar.button("AI Seasonal Insights"):
        st.session_state.nav = "AI Seasonal Insights"
if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ============ AI SEASONAL INSIGHTS DASHBOARD =============
# =========================================================
if role == "admin" and st.session_state.nav == "AI Seasonal Insights":
    st.header("📊 AI Seasonal Trend Insights")

    products = supabase.table("products").select("*").execute().data
    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}

    months = sorted({f"{s['month']} {s['year']}" for s in stmts}, reverse=True)
    sel_month = st.selectbox("Select Month", months)

    for prod in products:
        pname = prod["name"]
        pid = prod["id"]

        # Determine season
        month_name = sel_month.split()[0]

        if month_name in (prod.get("peak_season_months") or []):
            season = "Peak"
        elif month_name in (prod.get("high_season_months") or []):
            season = "High"
        elif month_name in (prod.get("low_season_months") or []):
            season = "Low"
        elif month_name in (prod.get("off_season_months") or []):
            season = "Off"
        else:
            season = "Neutral"

        # Fetch movement
        related_items = [
            i for i in items
            if i["product_id"] == pid
            and f"{next(s['month'] for s in stmts if s['id']==i['statement_id'])} "
            f"{next(s['year'] for s in stmts if s['id']==i['statement_id'])}" == sel_month
        ]

        if not related_items:
            continue

        total_issue = sum(i["issue"] for i in related_items)
        total_closing = sum(i["closing"] for i in related_items)

        # AI Insight Logic
        if season == "Peak" and total_issue == 0:
            severity = "🔴"
            insight = "Underperforming in peak season"
            reason = "Peak demand month but no movement recorded"
        elif season == "Off" and total_closing > 0:
            severity = "🟠"
            insight = "Stock buildup outside season"
            reason = "Off season but stock remains high"
        elif season == "Off":
            severity = "🟡"
            insight = "Seasonal slowdown is normal"
            reason = "Low movement expected in off season"
        elif season in ["High", "Peak"]:
            severity = "🟢"
            insight = "Seasonal demand behaving as expected"
            reason = "Movement aligns with season"
        else:
            continue

        with st.container(border=True):
            st.markdown(f"### {severity} {pname}")
            st.write(f"**Month:** {sel_month}")
            st.write(f"**Season Context:** {season}")
            st.write(f"**Issue:** {total_issue}")
            st.write(f"**Closing:** {total_closing}")
            st.write(f"**Insight:** {insight}")
            with st.expander("Why?"):
                st.write(reason)

st.write("---")
st.write("© Ivy Pharmaceuticals")
