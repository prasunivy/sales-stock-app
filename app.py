import streamlit as st
from supabase import create_client
from datetime import date

st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]

# ---------------- SESSION ----------------
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "home",
    "statement_id": None,
    "products": [],
    "product_index": 0
}.items():
    st.session_state.setdefault(k, v)

# ---------------- AUTH ----------------
def login(u, p):
    res = supabase.table("users").select("*")\
        .eq("username", u).eq("password", p).execute().data
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.rerun()
    st.error("Invalid login")

def logout():
    st.session_state.clear()
    st.rerun()

# ---------------- UTIL ----------------
def get_last_closing(pid, sid, year, month):
    stmts = supabase.table("sales_stock_statements")\
        .select("id,year,month")\
        .eq("stockist_id", sid)\
        .execute().data

    past = [s for s in stmts if (s["year"], MONTHS.index(s["month"])) < (year, MONTHS.index(month))]
    if not past:
        return 0

    last_stmt = max(past, key=lambda x: (x["year"], MONTHS.index(x["month"])))

    item = supabase.table("sales_stock_items")\
        .select("closing")\
        .eq("statement_id", last_stmt["id"])\
        .eq("product_id", pid)\
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
if role == "admin":
    navs = ["Lock Control"]
else:
    navs = ["Create / Resume"]

for n in navs:
    if st.sidebar.button(n):
        st.session_state.nav = n

if st.sidebar.button("Logout"):
    logout()

# ---------------- USER CREATE / RESUME ----------------
if role == "user" and st.session_state.nav == "Create / Resume":
    st.header("Create or Resume Statement")

    draft_stmt = supabase.table("sales_stock_statements")\
        .select("*")\
        .eq("user_id", st.session_state.user["id"])\
        .eq("status", "draft")\
        .execute().data

    if draft_stmt:
        if st.button("Resume Draft"):
            st.session_state.statement_id = draft_stmt[0]["id"]
            st.session_state.products = supabase.table("products").select("*").execute().data
            st.session_state.product_index = 0
            st.rerun()

    st.subheader("New Statement")

    allocs = supabase.table("user_stockists")\
        .select("*")\
        .eq("user_id", st.session_state.user["id"])\
        .execute().data

    stockists = supabase.table("stockists").select("*").execute().data
    smap = {s["name"]: s["id"] for s in stockists if s["id"] in [a["stockist_id"] for a in allocs]}

    sname = st.selectbox("Stockist", smap)
    year = st.selectbox("Year", [date.today().year, date.today().year - 1])
    month = st.selectbox("Month", MONTHS)

    if st.button("Start"):
        stmt = supabase.table("sales_stock_statements").insert({
            "user_id": st.session_state.user["id"],
            "stockist_id": smap[sname],
            "year": year,
            "month": month,
            "from_date": date.today().isoformat(),
            "to_date": date.today().isoformat(),
            "status": "draft",
            "locked": False
        }).execute()
        st.session_state.statement_id = stmt.data[0]["id"]
        st.session_state.products = supabase.table("products").select("*").execute().data
        st.session_state.product_index = 0
        st.rerun()

# ---------------- PRODUCT ENTRY (AUTO SAVE) ----------------
if role == "user" and st.session_state.statement_id:
    stmt = supabase.table("sales_stock_statements")\
        .select("*")\
        .eq("id", st.session_state.statement_id)\
        .execute().data[0]

    if stmt["locked"]:
        st.error("Statement locked by admin")
        st.stop()

    products = st.session_state.products
    idx = st.session_state.product_index
    if idx >= len(products):
        if st.button("Final Submit"):
            supabase.table("sales_stock_statements")\
                .update({"status": "final"})\
                .eq("id", st.session_state.statement_id)\
                .execute()
            st.success("Submitted")
            st.session_state.statement_id = None
            st.rerun()
        st.stop()

    prod = products[idx]
    pid = prod["id"]

    existing = supabase.table("sales_stock_items")\
        .select("*")\
        .eq("statement_id", st.session_state.statement_id)\
        .eq("product_id", pid)\
        .execute().data

    if existing:
        e = existing[0]
        opening = st.number_input("Opening", value=e["opening"], key=f"o{pid}")
        purchase = st.number_input("Purchase", value=e["purchase"], key=f"p{pid}")
        issue = st.number_input("Issue", value=e["issue"], key=f"i{pid}")
        closing = st.number_input("Closing", value=e["closing"], key=f"c{pid}")
    else:
        last_close = get_last_closing(pid, stmt["stockist_id"], stmt["year"], stmt["month"])
        opening = st.number_input("Opening", value=last_close, key=f"o{pid}")
        purchase = st.number_input("Purchase", value=0, key=f"p{pid}")
        issue = st.number_input("Issue", value=0, key=f"i{pid}")
        closing = st.number_input("Closing", value=0, key=f"c{pid}")

    diff = opening + purchase - issue - closing
    st.info(f"Difference: {diff}")

    if st.button("Save & Next"):
        supabase.table("sales_stock_items").upsert({
            "statement_id": st.session_state.statement_id,
            "product_id": pid,
            "opening": opening,
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "difference": diff
        }).execute()
        st.session_state.product_index += 1
        st.rerun()

# ---------------- ADMIN LOCK ----------------
if role == "admin" and st.session_state.nav == "Lock Control":
    st.header("Lock / Unlock Statements")
    for s in supabase.table("sales_stock_statements").select("*").execute().data:
        if st.button(f"{s['year']} {s['month']} — {'Unlock' if s['locked'] else 'Lock'}", key=s["id"]):
            supabase.table("sales_stock_statements")\
                .update({"locked": not s["locked"]})\
                .eq("id", s["id"]).execute()
            st.rerun()

st.write("© Ivy Pharmaceuticals")
