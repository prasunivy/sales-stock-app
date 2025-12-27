import streamlit as st
from supabase import create_client
from datetime import date, datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ---------------- SESSION ----------------
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "home",
    "statement_id": None,
    "edit_statement_id": None,
    "products": [],
    "product_index": 0
}.items():
    st.session_state.setdefault(k, v)

# ---------------- AUTH ----------------
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

# ---------------- UTIL ----------------
def get_last_closing(pid, stockist_id, year, month):
    stmts = supabase.table("sales_stock_statements") \
        .select("id,year,month") \
        .eq("stockist_id", stockist_id) \
        .execute().data

    past = [
        s for s in stmts
        if (s["year"], MONTHS.index(s["month"])) < (year, MONTHS.index(month))
    ]
    if not past:
        return 0

    last_stmt = max(past, key=lambda x: (x["year"], MONTHS.index(x["month"])))

    item = supabase.table("sales_stock_items") \
        .select("closing") \
        .eq("statement_id", last_stmt["id"]) \
        .eq("product_id", pid) \
        .execute().data

    return item[0]["closing"] if item else 0

# ---------------- LOGIN ----------------
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u, p)
    st.stop()

role = st.session_state.user["role"]

# ---------------- SIDEBAR ----------------
st.sidebar.title("Menu")
if role == "user":
    navs = ["Create / Resume"]
else:
    navs = ["Lock Control"]

for n in navs:
    if st.sidebar.button(n):
        st.session_state.nav = n
        st.session_state.edit_statement_id = None

if st.sidebar.button("Logout"):
    logout()

# ================= USER FLOW (UNCHANGED) =================
# (Your existing user flow remains exactly as before)

# ================= ADMIN — LOCK CONTROL =================
if role == "admin" and st.session_state.nav == "Lock Control" and not st.session_state.edit_statement_id:
    st.header("Admin — Lock Control")

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute().data

    for s in stmts:
        with st.container(border=True):
            created = datetime.fromisoformat(s["created_at"].replace("Z",""))

            st.write(f"**User:** {users.get(s['user_id'], 'Unknown')}")
            st.write(f"**Stockist:** {stockists.get(s['stockist_id'], 'Unknown')}")
            st.write(f"**Period:** {s['month']} {s['year']}")
            st.write(f"**Submitted:** {created.strftime('%d-%b-%Y %H:%M')}")
            st.write(f"**Status:** {'Locked' if s['locked'] else 'Open'}")

            c1, c2, c3 = st.columns(3)

            if c1.button("View", key=f"view_{s['id']}"):
                st.session_state.edit_statement_id = s["id"]
                st.session_state.view_only = True
                st.rerun()

            if not s["locked"] and c2.button("Edit", key=f"edit_{s['id']}"):
                st.session_state.edit_statement_id = s["id"]
                st.session_state.view_only = False
                st.rerun()

            if c3.button("Unlock" if s["locked"] else "Lock", key=f"lock_{s['id']}"):
                supabase.table("sales_stock_statements") \
                    .update({"locked": not s["locked"]}) \
                    .eq("id", s["id"]) \
                    .execute()
                st.rerun()

# ================= ADMIN — EDIT / VIEW =================
if role == "admin" and st.session_state.edit_statement_id:
    stmt = supabase.table("sales_stock_statements") \
        .select("*") \
        .eq("id", st.session_state.edit_statement_id) \
        .execute().data[0]

    products = supabase.table("products").select("*").execute().data
    items = supabase.table("sales_stock_items") \
        .select("*") \
        .eq("statement_id", stmt["id"]) \
        .execute().data

    item_map = {i["product_id"]: i for i in items}

    st.header("Admin Review / Edit Statement")

    st.write(f"**Month:** {stmt['month']} {stmt['year']}")
    st.write(f"**Locked:** {'Yes' if stmt['locked'] else 'No'}")

    st.write("---")

    updated_rows = []

    for p in products:
        if p["id"] not in item_map:
            continue

        i = item_map[p["id"]]

        st.subheader(p["name"])

        opening = i["opening"]
        purchase = i["purchase"]
        issue = i["issue"]
        closing = i["closing"]

        st.write(f"Opening: {opening}")

        if st.session_state.view_only or stmt["locked"]:
            st.write(f"Purchase: {purchase}")
            st.write(f"Issue: {issue}")
            st.write(f"Closing: {closing}")
        else:
            purchase = st.number_input(
                "Purchase", value=purchase, key=f"ap_{p['id']}"
            )
            issue = st.number_input(
                "Issue", value=issue, key=f"ai_{p['id']}"
            )
            closing = st.number_input(
                "Closing", value=closing, key=f"ac_{p['id']}"
            )

        diff = opening + purchase - issue - closing
        st.info(f"Difference: {diff}")

        updated_rows.append({
            "statement_id": stmt["id"],
            "product_id": p["id"],
            "opening": opening,
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "difference": diff
        })

        st.write("---")

    if not stmt["locked"] and not st.session_state.view_only:
        if st.button("Save Changes"):
            for r in updated_rows:
                supabase.table("sales_stock_items") \
                    .upsert(r, on_conflict="statement_id,product_id") \
                    .execute()
            st.success("Changes saved")

    if st.button("Back to Lock Control"):
        st.session_state.edit_statement_id = None
        st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
