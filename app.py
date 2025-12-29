import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTH_ORDER = [
    "April","May","June","July","August","September",
    "October","November","December","January","February","March"
]

# ================= SESSION =================
for k in [
    "logged_in","user","nav",
    "statement_id","product_index",
    "edit_user","edit_product","edit_stockist","edit_statement"
]:
    st.session_state.setdefault(k, None)

# ================= HELPERS =================
def safe_select(table, **filters):
    q = supabase.table(table).select("*")
    for k,v in filters.items():
        q = q.eq(k,v)
    return q.execute().data or []

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
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True):
        login(u,p)
    st.stop()

user = st.session_state.user
role = user["role"]
uid = user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role=="admin":
    if st.sidebar.button("Users"): st.session_state.nav="Users"
    if st.sidebar.button("Products"): st.session_state.nav="Products"
    if st.sidebar.button("Stockists"): st.session_state.nav="Stockists"
    if st.sidebar.button("Allocate"): st.session_state.nav="Allocate"
    if st.sidebar.button("Matrix"): st.session_state.nav="Matrix"
    if st.sidebar.button("Advanced KPI"): st.session_state.nav="Advanced KPI"

if role=="user":
    if st.sidebar.button("My Statements"): st.session_state.nav="My Statements"
    if st.sidebar.button("New Statement"): st.session_state.nav="New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — PRODUCTS ======================
# =========================================================
if role=="admin" and st.session_state.nav=="Products":
    st.header("📦 Products")

    with st.form("add_product"):
        name = st.text_input("Product Name")
        peak = st.number_input("Peak")
        high = st.number_input("High")
        low = st.number_input("Low")
        lowest = st.number_input("Lowest")
        if st.form_submit_button("Add Product", use_container_width=True):
            supabase.table("products").insert({
                "name":name,"peak":peak,"high":high,"low":low,"lowest":lowest
            }).execute()
            st.rerun()

    st.subheader("Existing Products")
    for p in safe_select("products"):
        c1,c2,c3 = st.columns([6,2,2])
        c1.write(
            f"{p['name']} | Peak:{p['peak']} High:{p['high']} "
            f"Low:{p['low']} Lowest:{p['lowest']}"
        )
        if c2.button("✏️ Edit", key=f"ep{p['id']}"):
            st.session_state.edit_product = p
        if c3.button("🗑 Delete", key=f"dp{p['id']}"):
            supabase.table("products").delete().eq("id",p["id"]).execute()
            st.rerun()

    if st.session_state.edit_product:
        p = st.session_state.edit_product
        with st.form("edit_product"):
            name = st.text_input("Name", p["name"])
            peak = st.number_input("Peak", value=p["peak"])
            high = st.number_input("High", value=p["high"])
            low = st.number_input("Low", value=p["low"])
            lowest = st.number_input("Lowest", value=p["lowest"])
            if st.form_submit_button("Update", use_container_width=True):
                supabase.table("products").update({
                    "name":name,"peak":peak,"high":high,
                    "low":low,"lowest":lowest
                }).eq("id",p["id"]).execute()
                st.session_state.edit_product=None
                st.rerun()

# =========================================================
# ================= ADMIN — ALLOCATE ======================
# =========================================================
if role=="admin" and st.session_state.nav=="Allocate":
    st.header("🔗 Allocate Stockists")

    users = safe_select("users")
    stockists = safe_select("stockists")
    allocations = safe_select("user_stockist")

    with st.form("allocate"):
        u = st.selectbox("User", users, format_func=lambda x:x["username"])
        s = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
        if st.form_submit_button("Allocate", use_container_width=True):
            supabase.table("user_stockist").insert({
                "user_id":u["id"],"stockist_id":s["id"]
            }).execute()
            st.rerun()

    st.subheader("Current Allocations")
    umap = {u["id"]:u["username"] for u in users}
    smap = {s["id"]:s["name"] for s in stockists}

    for a in allocations:
        c1,c2,c3 = st.columns([5,5,2])
        c1.write(umap.get(a["user_id"]))
        c2.write(smap.get(a["stockist_id"]))
        if c3.button("🗑 Remove", key=f"da{a['id']}"):
            supabase.table("user_stockist").delete().eq("id",a["id"]).execute()
            st.rerun()

# =========================================================
# ================= ADMIN — MATRIX ========================
# =========================================================
if role=="admin" and st.session_state.nav=="Matrix":
    st.header("📊 Matrix")

    stmts = safe_select("sales_stock_statements")
    items = safe_select("sales_stock_items")
    products = safe_select("products")

    if not stmts:
        st.info("No data available")
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
                    "Opening":sum(i["opening"] for i in pi),
                    "Purchase":sum(i["purchase"] for i in pi),
                    "Issue":sum(i["issue"] for i in pi),
                    "Closing":sum(i["closing"] for i in pi),
                    "Difference":sum(i["difference"] for i in pi)
                })

        st.dataframe(pd.DataFrame(rows), use_container_width=True)

# =========================================================
# ================= ADMIN — ADVANCED KPI ==================
# =========================================================
if role=="admin" and st.session_state.nav=="Advanced KPI":
    st.header("📈 Advanced KPI")

    items = safe_select("sales_stock_items")
    products = safe_select("products")

    if not items:
        st.info("No data available")
    else:
        df = pd.DataFrame(items)
        kpi = df.groupby("product_id").agg(
            issue=("issue","sum"),
            closing=("closing","sum")
        ).reset_index()

        pmap = {p["id"]:p["name"] for p in products}
        kpi["Product"] = kpi["product_id"].map(pmap)

        st.subheader("High Closing Stock")
        st.dataframe(kpi.sort_values("closing", ascending=False),
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
        st.warning("No stockist allocated. Contact admin.")
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
