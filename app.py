import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from supabase import create_client
from datetime import datetime

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide",
    initial_sidebar_state="expanded"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

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
def safe_select(table):
    try:
        return supabase.table(table).select("*").execute().data or []
    except Exception:
        st.error(f"Failed to load {table}")
        return []

def safe_insert(table, payload):
    try:
        supabase.table(table).insert(payload).execute()
        return True
    except Exception:
        st.error(f"Insert failed: {table}")
        return False

def login(username, password):
    users = safe_select("users")
    match = [u for u in users if u.get("username")==username and u.get("password")==password]
    if match:
        st.session_state.logged_in = True
        st.session_state.user = match[0]
        st.session_state.nav = "Users" if match[0]["role"]=="admin" else "My Statements"
        st.rerun()
    else:
        st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

# ======================================================
# LOGIN (STABLE)
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
# SIDEBAR NAVIGATION
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
if role=="admin" and st.session_state.nav=="Users":
    st.header("👤 Users")

    with st.form("add_user"):
        uname = st.text_input("Username")
        pwd = st.text_input("Password")
        r = st.selectbox("Role", ["user","admin"])
        if st.form_submit_button("Add User", use_container_width=True):
            safe_insert("users", {"username":uname,"password":pwd,"role":r})
            st.rerun()

    for u in safe_select("users"):
        st.write(f"{u.get('username')} ({u.get('role')})")

# ======================================================
# ADMIN — PRODUCTS
# ======================================================
if role=="admin" and st.session_state.nav=="Products":
    st.header("📦 Products")

    with st.form("add_product"):
        name = st.text_input("Product Name")
        peak = st.number_input("Peak",0)
        high = st.number_input("High",0)
        low = st.number_input("Low",0)
        lowest = st.number_input("Lowest",0)
        if st.form_submit_button("Add Product", use_container_width=True):
            safe_insert("products", {
                "name":name,
                "peak":peak,
                "high":high,
                "low":low,
                "lowest":lowest
            })
            st.rerun()

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
if role=="admin" and st.session_state.nav=="Stockists":
    st.header("🏪 Stockists")

    with st.form("add_stockist"):
        name = st.text_input("Stockist Name")
        if st.form_submit_button("Add Stockist", use_container_width=True):
            safe_insert("stockists", {"name":name})
            st.rerun()

    for s in safe_select("stockists"):
        st.write(s.get("name"))

# ======================================================
# ADMIN — ALLOCATE (SCHEMA-AGNOSTIC)
# ======================================================
if role=="admin" and st.session_state.nav=="Allocate":
    st.header("🔗 Allocate Stockists")

    users = safe_select("users")
    stockists = safe_select("stockists")
    allocations = safe_select("user_stockist")

    with st.form("allocate"):
        u = st.selectbox("User", users, format_func=lambda x:x["username"])
        s = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
        if st.form_submit_button("Allocate", use_container_width=True):
            safe_insert("user_stockist", {
                list({k for k in u.keys() if "id" in k.lower()})[0]: u["id"],
                list({k for k in s.keys() if "id" in k.lower()})[0]: s["id"]
            })
            st.success("Allocated")

    st.subheader("Existing Allocations")
    for a in allocations:
        st.write(a)

# ======================================================
# USER — MY STATEMENTS
# ======================================================
if role=="user" and st.session_state.nav=="My Statements":
    st.header("📄 My Statements")

    stmts = safe_select("sales_stock_statements")
    stockists = safe_select("stockists")
    smap = {s["id"]:s["name"] for s in stockists}

    my_stmts = [s for s in stmts if s.get("user_id")==uid]

    if not my_stmts:
        st.info("No statements yet")

    for s in my_stmts:
        st.write(
            f"{s.get('month')} {s.get('year')} | "
            f"{smap.get(s.get('stockist_id'),'—')} | "
            f"{s.get('status')}"
        )

# ======================================================
# USER — NEW STATEMENT (SCHEMA-AGNOSTIC)
# ======================================================
if role=="user" and st.session_state.nav=="New Statement":
    st.header("📝 New Statement")

    all_maps = safe_select("user_stockist")
    my_maps = [m for m in all_maps if uid in m.values()]

    stockists = safe_select("stockists")
    stockists = [s for s in stockists if s["id"] in [m.get("stockist_id") for m in my_maps]]

    if not stockists:
        st.warning("No stockist allocated. Contact admin.")
    else:
        with st.form("create_stmt"):
            stck = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
            month = st.selectbox("Month", MONTH_ORDER)
            year = st.number_input("Year", value=datetime.now().year)
            if st.form_submit_button("Create Statement", use_container_width=True):
                safe_insert("sales_stock_statements", {
                    "user_id":uid,
                    "stockist_id":stck["id"],
                    "month":month,
                    "year":int(year),
                    "status":"draft",
                    "locked":False
                })
                st.success("Statement created")

st.write("---")
st.write("© Ivy Pharmaceuticals")
