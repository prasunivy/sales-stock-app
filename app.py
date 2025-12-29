import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
from fpdf import FPDF

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTH_ORDER = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]

# ================= SESSION =================
for k in [
    "logged_in","user","nav","statement_id","product_index",
    "edit_user","edit_product","edit_stockist"
]:
    st.session_state.setdefault(k, None)

# ================= HELPERS =================
def safe_select(table, **filters):
    try:
        q = supabase.table(table).select("*")
        for k,v in filters.items():
            q = q.eq(k,v)
        return q.execute().data or []
    except:
        return []

def login(u,p):
    res = safe_select("users", username=u.strip(), password=p.strip())
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.session_state.nav = "Users" if res[0]["role"]=="admin" else "New Statement"
        st.rerun()
    st.error("Invalid credentials")

def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

# ================= LOGIN =================
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u,p)
    st.stop()

user = st.session_state.user
role = user["role"]
uid = user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role=="admin":
    for m in ["Users","Products","Stockists","Allocate","Matrix","Advanced KPI"]:
        if st.sidebar.button(m): st.session_state.nav = m

if role=="user":
    if st.sidebar.button("New Statement"):
        st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — ADVANCED KPI ==================
# =========================================================
if role=="admin" and st.session_state.nav=="Advanced KPI":
    st.header("📊 Advanced KPI — Stock Intelligence")

    stmts = safe_select("sales_stock_statements")
    items = safe_select("sales_stock_items")
    products = safe_select("products")
    stockists = safe_select("stockists")
    users = safe_select("users")

    years = sorted({s["year"] for s in stmts}, reverse=True)
    year = st.selectbox("Year", years)
    months = st.multiselect("Months", MONTH_ORDER, default=MONTH_ORDER[-3:])

    stmt_ids = [
        s["id"] for s in stmts
        if s["year"]==year and s["month"] in months
    ]

    kpi_tab = st.tabs(["📈 Stock Trend","🧊 Idle Stock","⚠️ High Closing Risk"])

    # ================= STOCK TREND =================
    with kpi_tab[0]:
        rows = []
        for p in products:
            p_items = [i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if len(p_items)>=2:
                p_items = sorted(p_items, key=lambda x: x["statement_id"])
                change = p_items[-1]["closing"] - p_items[0]["closing"]
                rows.append({
                    "Product": p["name"],
                    "Opening": p_items[0]["opening"],
                    "Closing": p_items[-1]["closing"],
                    "Net Change": change,
                    "Trend": "Growth" if change>0 else "Degrowth" if change<0 else "Stable"
                })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No trend data available.")

    # ================= IDLE STOCK =================
    with kpi_tab[1]:
        rows = []
        for p in products:
            p_items = [i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            idle_months = sum(1 for i in p_items if i["issue"]==0 and i["closing"]>0)
            if idle_months>=2:
                rows.append({
                    "Product": p["name"],
                    "Closing Stock": max(i["closing"] for i in p_items),
                    "Idle Months": idle_months,
                    "Risk": "High" if idle_months>=3 else "Medium"
                })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No idle stock detected.")

    # ================= HIGH CLOSING RISK =================
    with kpi_tab[2]:
        rows = []
        for p in products:
            p_items = [i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if len(p_items)>=2:
                avg_issue = sum(i["issue"] for i in p_items)/len(p_items)
                closing = p_items[-1]["closing"]
                if avg_issue>0:
                    ratio = round(closing/avg_issue,2)
                    if ratio>1.5:
                        rows.append({
                            "Product": p["name"],
                            "Avg Issue": round(avg_issue,2),
                            "Closing": closing,
                            "Coverage Ratio": ratio,
                            "Risk": "Critical" if ratio>3 else "High"
                        })
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No high closing risk found.")

st.write("---")
st.write("© Ivy Pharmaceuticals")
