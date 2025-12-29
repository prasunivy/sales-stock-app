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
        if not st.session_state.nav:
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
    if st.sidebar.button("Users"): st.session_state.nav = "Users"
    if st.sidebar.button("Products"): st.session_state.nav = "Products"
    if st.sidebar.button("Stockists"): st.session_state.nav = "Stockists"
    if st.sidebar.button("Allocate"): st.session_state.nav = "Allocate"
    if st.sidebar.button("Matrix"): st.session_state.nav = "Matrix"
    if st.sidebar.button("Advanced KPI"): st.session_state.nav = "Advanced KPI"

if role=="user":
    if st.sidebar.button("My Statements"): st.session_state.nav = "My Statements"
    if st.sidebar.button("New Statement"): st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — USERS =========================
# =========================================================
if role=="admin" and st.session_state.nav=="Users":
    st.header("👤 Users")

    with st.form("add_user"):
        uname = st.text_input("Username")
        pwd = st.text_input("Password")
        r = st.selectbox("Role", ["user","admin"])
        if st.form_submit_button("Add User", use_container_width=True):
            supabase.table("users").insert({
                "username":uname,"password":pwd,"role":r
            }).execute()
            st.rerun()

    for u in safe_select("users"):
        c1,c2,c3 = st.columns([4,3,2])
        c1.write(u["username"])
        c2.write(u["role"])
        if c3.button("🗑 Delete", key=f"du{u['id']}"):
            supabase.table("users").delete().eq("id", u["id"]).execute()
            st.rerun()

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
            f"{p['name']} | P:{p.get('peak')} H:{p.get('high')} "
            f"L:{p.get('low')} LL:{p.get('lowest')}"
        )

# =========================================================
# ================= ADMIN — STOCKISTS =====================
# =========================================================
if role=="admin" and st.session_state.nav=="Stockists":
    st.header("🏪 Stockists")

    with st.form("add_stockist"):
        sname = st.text_input("Stockist Name")
        if st.form_submit_button("Add Stockist", use_container_width=True):
            supabase.table("stockists").insert({"name":sname}).execute()
            st.rerun()

    for s in safe_select("stockists"):
        st.write(s["name"])

# =========================================================
# ================= ADMIN — ALLOCATE ======================
# =========================================================
if role=="admin" and st.session_state.nav=="Allocate":
    st.header("🔗 Allocate Stockists")

    users = safe_select("users")
    stockists = safe_select("stockists")

    with st.form("allocate_stockist"):
        u = st.selectbox("User", users, format_func=lambda x:x["username"])
        s = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
        if st.form_submit_button("Allocate", use_container_width=True):
            supabase.table("user_stockist").insert({
                "user_id":u["id"],
                "stockist_id":s["id"]
            }).execute()
            st.success("Allocated")

# =========================================================
# ================= USER — MY STATEMENTS ==================
# =========================================================
if role=="user" and st.session_state.nav=="My Statements":
    st.header("📄 My Statements")

    stmts = safe_select("sales_stock_statements", user_id=uid)
    stockists = safe_select("stockists")
    smap = {s["id"]:s["name"] for s in stockists}

    for s in stmts:
        c1,c2,c3,c4 = st.columns([3,3,3,2])
        c1.write(f"{s['month']} {s['year']}")
        c2.write(smap.get(s["stockist_id"],"—"))
        c3.write(s["status"])
        if c4.button("✏️ Edit", key=f"es{s['id']}"):
            st.session_state.edit_statement = s["id"]
            st.session_state.nav = "Edit Statement"
            st.rerun()

# =========================================================
# ================= USER — EDIT STATEMENT =================
# =========================================================
if role=="user" and st.session_state.nav=="Edit Statement":
    st.header("✏️ Edit Statement")

    stmt_id = st.session_state.edit_statement
    products = safe_select("products")
    items = safe_select("sales_stock_items", statement_id=stmt_id)

    for item in items:
        p = next(x for x in products if x["id"] == item["product_id"])
        with st.form(f"edit_{item['id']}"):
            st.subheader(p["name"])
            o = st.number_input("Opening", value=item["opening"])
            pu = st.number_input("Purchase", value=item["purchase"])
            i = st.number_input("Issue", value=item["issue"])
            c = st.number_input("Closing", value=item["closing"])
            d = o + pu - i - c
            st.write(f"Difference: {d}")
            if st.form_submit_button("Update", use_container_width=True):
                supabase.table("sales_stock_items").update({
                    "opening":o,"purchase":pu,
                    "issue":i,"closing":c,
                    "difference":d
                }).eq("id", item["id"]).execute()

    if st.button("Re-submit Statement", use_container_width=True):
        supabase.table("sales_stock_statements") \
            .update({"status":"final","locked":True}) \
            .eq("id", stmt_id).execute()
        st.session_state.nav = "My Statements"
        st.session_state.edit_statement = None
        st.rerun()

# =========================================================
# ================= USER — NEW STATEMENT ==================
# =========================================================
if role=="user" and st.session_state.nav=="New Statement":
    st.header("📝 New Statement")

    mappings = safe_select("user_stockist", user_id=uid)
    stockist_ids = [m["stockist_id"] for m in mappings]
    stockists = [s for s in safe_select("stockists") if s["id"] in stockist_ids]

    with st.form("create_statement"):
        stck = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
        month = st.selectbox("Month", MONTH_ORDER)
        year = st.number_input("Year", value=datetime.now().year)
        if st.form_submit_button("Create Statement", use_container_width=True):
            res = supabase.table("sales_stock_statements").insert({
                "user_id":uid,
                "stockist_id":stck["id"],
                "month":month,
                "year":int(year),
                "status":"draft",
                "locked":False
            }).execute()
            st.session_state.statement_id = res.data[0]["id"]
            st.session_state.product_index = 0
            st.rerun()

# =========================================================
# ================= PRODUCT ENTRY (A–Z) ===================
# =========================================================
if role=="user" and st.session_state.statement_id:
    products = sorted(
        safe_select("products"),
        key=lambda x:(x.get("name") or "").lower()
    )
    idx = st.session_state.product_index

    if idx >= len(products):
        supabase.table("sales_stock_statements") \
            .update({"status":"final","locked":True}) \
            .eq("id", st.session_state.statement_id).execute()
        st.success("Statement submitted")
        st.session_state.statement_id = None
        st.stop()

    p = products[idx]

    with st.form("product_entry"):
        st.subheader(p["name"])
        o = st.number_input("Opening",0)
        pu = st.number_input("Purchase",0)
        i = st.number_input("Issue",0)
        c = st.number_input("Closing",0)
        d = o + pu - i - c
        st.write(f"Difference: {d}")
        if st.form_submit_button("Save & Next", use_container_width=True):
            supabase.table("sales_stock_items").insert({
                "statement_id":st.session_state.statement_id,
                "product_id":p["id"],
                "opening":o,"purchase":pu,
                "issue":i,"closing":c,
                "difference":d
            }).execute()
            st.session_state.product_index += 1
            st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
