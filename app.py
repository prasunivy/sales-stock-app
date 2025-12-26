import streamlit as st
from supabase import create_client
from datetime import date
import pandas as pd

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ================= SESSION INIT =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "home",
    "statement_id": None,
    "product_index": 0,
    "product_cache": [],
    "draft_data": {}
}.items():
    st.session_state.setdefault(k, v)

# ================= HELPERS =================
def safe_next(iterable):
    return next(iter(iterable), None)

def logout():
    st.session_state.clear()
    st.rerun()

def login(u, p):
    res = supabase.table("users").select("*")\
        .eq("username", u.strip()).eq("password", p.strip()).execute().data
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.rerun()
    else:
        st.error("Invalid credentials")

def get_last_closing(product_id, stockist_id, year, month):
    stmts = supabase.table("sales_stock_statements")\
        .select("id,year,month")\
        .eq("stockist_id", stockist_id)\
        .lt("year", year)\
        .execute().data

    if not stmts:
        return 0

    latest_stmt = max(stmts, key=lambda s: (s["year"], MONTHS.index(s["month"])))
    item = supabase.table("sales_stock_items")\
        .select("closing")\
        .eq("statement_id", latest_stmt["id"])\
        .eq("product_id", product_id)\
        .execute().data

    return item[0]["closing"] if item else 0

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
st.sidebar.title("Navigation")

if role == "admin":
    navs = ["Users","Products","Stockists","Allocate","Statements","Lock Control"]
else:
    navs = ["Create Statement","My Statements"]

for n in navs:
    if st.sidebar.button(n):
        st.session_state.nav = n

if st.sidebar.button("Logout"):
    logout()

# ================= ADMIN — USER MGMT =================
if role == "admin" and st.session_state.nav == "Users":
    st.header("Manage Users")

    users = supabase.table("users").select("*").execute().data

    with st.expander("Add User"):
        u = st.text_input("Username")
        p = st.text_input("Password")
        r = st.selectbox("Role", ["user","admin"])
        if st.button("Create"):
            supabase.table("users").insert({
                "username": u, "password": p, "role": r
            }).execute()
            st.success("User added")
            st.rerun()

    for us in users:
        st.write(us["username"], us["role"])

# ================= USER — CREATE STATEMENT =================
if role == "user" and st.session_state.nav == "Create Statement":
    st.header("Create Sales & Stock Statement")

    allocs = supabase.table("user_stockists").select("*")\
        .eq("user_id", st.session_state.user["id"]).execute().data
    if not allocs:
        st.warning("No stockists allocated")
        st.stop()

    stockists = supabase.table("stockists").select("*").execute().data
    s_map = {s["name"]: s["id"] for s in stockists if s["id"] in [a["stockist_id"] for a in allocs]}

    sname = st.selectbox("Stockist", s_map.keys())
    year = st.selectbox("Year", [date.today().year, date.today().year-1])
    month = st.selectbox("Month", MONTHS)

    if st.button("Start / Resume"):
        stmt = supabase.table("sales_stock_statements").insert({
            "user_id": st.session_state.user["id"],
            "stockist_id": s_map[sname],
            "year": year,
            "month": month,
            "status": "draft",
            "locked": False
        }).execute()

        st.session_state.statement_id = stmt.data[0]["id"]
        st.session_state.product_cache = supabase.table("products").select("*").execute().data
        st.session_state.product_index = 0
        st.session_state.draft_data = {}
        st.rerun()

# ================= PRODUCT ENTRY =================
if role == "user" and st.session_state.statement_id:
    products = st.session_state.product_cache
    idx = st.session_state.product_index

    if idx >= len(products):
        st.success("All products entered")
        if st.button("Final Submit"):
            for pid, d in st.session_state.draft_data.items():
                supabase.table("sales_stock_items").upsert({
                    "statement_id": st.session_state.statement_id,
                    "product_id": pid,
                    **d
                }).execute()
            supabase.table("sales_stock_statements")\
                .update({"status": "final"})\
                .eq("id", st.session_state.statement_id).execute()
            st.success("Submitted")
            st.session_state.statement_id = None
            st.rerun()
        st.stop()

    prod = products[idx]
    st.subheader(prod["name"])

    stmt = supabase.table("sales_stock_statements")\
        .select("*").eq("id", st.session_state.statement_id).execute().data[0]

    last_close = get_last_closing(
        prod["id"], stmt["stockist_id"], stmt["year"], stmt["month"]
    )

    opening = st.number_input("Opening", value=last_close)
    purchase = st.number_input("Purchase", value=0)
    issue = st.number_input("Issue", value=0)
    closing = st.number_input("Closing", value=0)

    diff = opening + purchase - issue - closing
    st.info(f"Difference: {diff}")

    st.session_state.draft_data[prod["id"]] = {
        "opening": opening,
        "purchase": purchase,
        "issue": issue,
        "closing": closing,
        "difference": diff
    }

    col = st.columns(2)
    if col[0].button("Next"):
        st.session_state.product_index += 1
        st.rerun()
    if idx > 0 and col[1].button("Previous"):
        st.session_state.product_index -= 1
        st.rerun()

# ================= ADMIN — LOCK CONTROL =================
if role == "admin" and st.session_state.nav == "Lock Control":
    st.header("Lock / Unlock Statements")

    stmts = supabase.table("sales_stock_statements").select("*").execute().data

    for s in stmts:
        col = st.columns(4)
        col[0].write(f"{s['year']} {s['month']}")
        col[1].write(s["status"])
        col[2].write("Locked" if s["locked"] else "Open")
        if not s["locked"] and col[3].button("Lock", key=f"l{s['id']}"):
            supabase.table("sales_stock_statements")\
                .update({"locked": True}).eq("id", s["id"]).execute()
            st.rerun()
        if s["locked"] and col[3].button("Unlock", key=f"u{s['id']}"):
            supabase.table("sales_stock_statements")\
                .update({"locked": False}).eq("id", s["id"]).execute()
            st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
