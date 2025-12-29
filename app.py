import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

MONTH_ORDER = [
    "April","May","June","July","August","September",
    "October","November","December","January","February","March"
]

# ================= SESSION =================
for k in [
    "logged_in","user","nav",
    "statement_id","product_index","edit_statement"
]:
    st.session_state.setdefault(k, None)

# ================= HELPERS =================
def safe_select(table, **filters):
    try:
        q = supabase.table(table).select("*")
        for k,v in filters.items():
            q = q.eq(k,v)
        return q.execute().data or []
    except Exception as e:
        st.error(f"{table} load failed")
        return []

def login(u,p):
    res = safe_select("users", username=u.strip(), password=p.strip())
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.session_state.nav = "Users" if res[0]["role"]=="admin" else "My Statements"
        st.rerun()
    st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

# ================= LOGIN =================
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    if st.button("Login"):
        login(
            st.text_input("Username"),
            st.text_input("Password", type="password")
        )
    st.stop()

user = st.session_state.user
role = user["role"]
uid = user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role=="admin":
    for m in ["Users","Products","Stockists","Allocate","Matrix","Advanced KPI"]:
        if st.sidebar.button(m):
            st.session_state.nav = m

if role=="user":
    for m in ["My Statements","New Statement"]:
        if st.sidebar.button(m):
            st.session_state.nav = m

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — USERS =========================
# =========================================================
if role=="admin" and st.session_state.nav=="Users":
    st.header("👤 Users")
    users = safe_select("users")
    if not users:
        st.info("No users found")
    for u in users:
        st.write(u["username"], "-", u["role"])

# =========================================================
# ================= ADMIN — PRODUCTS ======================
# =========================================================
if role=="admin" and st.session_state.nav=="Products":
    st.header("📦 Products")

    with st.form("add_product"):
        name = st.text_input("Product Name")
        peak = st.number_input("Peak",0)
        high = st.number_input("High",0)
        low = st.number_input("Low",0)
        lowest = st.number_input("Lowest",0)
        if st.form_submit_button("Add Product", use_container_width=True):
            supabase.table("products").insert({
                "name":name,"peak":peak,"high":high,"low":low,"lowest":lowest
            }).execute()
            st.rerun()

    for p in safe_select("products"):
        st.write(
            f"{p.get('name')} | "
            f"Peak:{p.get('peak',0)} "
            f"High:{p.get('high',0)} "
            f"Low:{p.get('low',0)} "
            f"Lowest:{p.get('lowest',0)}"
        )

# =========================================================
# ================= ADMIN — STOCKISTS =====================
# =========================================================
if role=="admin" and st.session_state.nav=="Stockists":
    st.header("🏪 Stockists")
    stockists = safe_select("stockists")
    if not stockists:
        st.info("No stockists found")
    for s in stockists:
        st.write(s["name"])

# =========================================================
# ================= ADMIN — ALLOCATE ======================
# =========================================================
if role=="admin" and st.session_state.nav=="Allocate":
    st.header("🔗 Allocate Stockists")

    users = safe_select("users")
    stockists = safe_select("stockists")

    if not users or not stockists:
        st.warning("Users or stockists missing")
    else:
        with st.form("allocate"):
            u = st.selectbox("User", users, format_func=lambda x:x["username"])
            s = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
            if st.form_submit_button("Allocate", use_container_width=True):
                supabase.table("user_stockist").insert({
                    "user_id":u["id"],"stockist_id":s["id"]
                }).execute()
                st.success("Allocated")

# =========================================================
# ================= ADMIN — MATRIX ========================
# =========================================================
if role=="admin" and st.session_state.nav=="Matrix":
    st.header("📊 Matrix")

    stmts = safe_select("sales_stock_statements")
    items = safe_select("sales_stock_items")
    products = safe_select("products")

    if not stmts:
        st.info("No statements")
    else:
        year = st.selectbox("Year", sorted({s["year"] for s in stmts}, reverse=True))
        month = st.selectbox("Month", MONTH_ORDER)

        stmt_ids = {s["id"] for s in stmts if s["year"]==year and s["month"]==month}
        rows=[]
        for p in products:
            pi=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if pi:
                rows.append({
                    "Product":p["name"],
                    "Issue":sum(i["issue"] for i in pi),
                    "Closing":sum(i["closing"] for i in pi)
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

# =========================================================
# ================= ADMIN — ADVANCED KPI ==================
# =========================================================
if role=="admin" and st.session_state.nav=="Advanced KPI":
    st.header("📈 Advanced KPI")

    items = safe_select("sales_stock_items")
    if not items:
        st.info("No data")
    else:
        df = pd.DataFrame(items)
        st.dataframe(df.groupby("product_id")[["issue","closing"]].sum().reset_index(),
                     use_container_width=True)

# =========================================================
# ================= USER — NEW STATEMENT ==================
# =========================================================
if role=="user" and st.session_state.nav=="New Statement":
    st.header("📝 New Statement")

    mappings = safe_select("user_stockist", user_id=uid)
    stockists = safe_select("stockists")
    stockists = [s for s in stockists if s["id"] in [m["stockist_id"] for m in mappings]]

    if not stockists:
        st.warning("No stockist allocated")
    else:
        with st.form("create_stmt"):
            stck = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
            month = st.selectbox("Month", MONTH_ORDER)
            year = st.number_input("Year", value=datetime.now().year)
            if st.form_submit_button("Create", use_container_width=True):
                res = supabase.table("sales_stock_statements").insert({
                    "user_id":uid,"stockist_id":stck["id"],
                    "month":month,"year":year,
                    "status":"draft","locked":False
                }).execute()
                st.session_state.statement_id = res.data[0]["id"]
                st.session_state.product_index = 0
                st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
