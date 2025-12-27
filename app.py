import streamlit as st
from supabase import create_client
from datetime import date

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
defaults = {
    "logged_in": False,
    "user": None,
    "nav": "home",
    "statement_id": None,
    "product_index": 0,
    "products": [],
    "draft": {},
    "confirm_submit": False
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ================= AUTH =================
def login(u, p):
    res = supabase.table("users").select("*")\
        .eq("username", u.strip()).eq("password", p.strip()).execute().data
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.rerun()
    else:
        st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

# ================= UTIL =================
def get_last_closing(product_id, stockist_id, year, month):
    stmts = supabase.table("sales_stock_statements")\
        .select("id,year,month")\
        .eq("stockist_id", stockist_id)\
        .execute().data

    past = [
        s for s in stmts
        if (s["year"] < year) or
           (s["year"] == year and MONTHS.index(s["month"]) < MONTHS.index(month))
    ]

    if not past:
        return 0

    latest = max(past, key=lambda s: (s["year"], MONTHS.index(s["month"])))

    item = supabase.table("sales_stock_items")\
        .select("closing")\
        .eq("statement_id", latest["id"])\
        .eq("product_id", product_id)\
        .execute().data

    return item[0]["closing"] if item else 0

def load_existing_items(statement_id):
    rows = supabase.table("sales_stock_items")\
        .select("*")\
        .eq("statement_id", statement_id)\
        .execute().data

    draft = {}
    for r in rows:
        draft[r["product_id"]] = {
            "opening": r["opening"],
            "purchase": r["purchase"],
            "issue": r["issue"],
            "closing": r["closing"],
            "difference": r["difference"]
        }
    return draft

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
    navs = ["Lock Control"]
else:
    navs = ["Create / Resume Statement"]

for n in navs:
    if st.sidebar.button(n):
        st.session_state.nav = n

if st.sidebar.button("Logout"):
    logout()

# ================= USER — CREATE / RESUME =================
if role == "user" and st.session_state.nav == "Create / Resume Statement":
    st.header("Create or Resume Statement")

    draft_stmt = supabase.table("sales_stock_statements")\
        .select("*")\
        .eq("user_id", st.session_state.user["id"])\
        .eq("status", "draft")\
        .execute().data

    if draft_stmt:
        st.info("Unfinished statement found.")
        if st.button("Resume Draft"):
            st.session_state.statement_id = draft_stmt[0]["id"]
            st.session_state.products = supabase.table("products").select("*").execute().data
            st.session_state.draft = load_existing_items(st.session_state.statement_id)

            # Resume at first unfilled product
            for i, p in enumerate(st.session_state.products):
                if p["id"] not in st.session_state.draft:
                    st.session_state.product_index = i
                    break
            else:
                st.session_state.product_index = len(st.session_state.products)

            st.rerun()

    st.subheader("Create New Statement")

    allocs = supabase.table("user_stockists")\
        .select("*")\
        .eq("user_id", st.session_state.user["id"])\
        .execute().data

    if not allocs:
        st.warning("No stockist allocated")
        st.stop()

    stockists = supabase.table("stockists").select("*").execute().data
    smap = {s["name"]: s["id"] for s in stockists if s["id"] in [a["stockist_id"] for a in allocs]}

    sname = st.selectbox("Stockist", smap.keys())
    year = st.selectbox("Year", [date.today().year, date.today().year - 1])
    month = st.selectbox("Month", MONTHS)

    if st.button("Start New Statement"):
        stmt = supabase.table("sales_stock_statements").insert({
            "user_id": st.session_state.user["id"],
            "stockist_id": smap[sname],
            "year": int(year),
            "month": month,
            "from_date": date.today().isoformat(),
            "to_date": date.today().isoformat(),
            "status": "draft",
            "locked": False
        }).execute()

        st.session_state.statement_id = stmt.data[0]["id"]
        st.session_state.products = supabase.table("products").select("*").execute().data
        st.session_state.product_index = 0
        st.session_state.draft = {}
        st.rerun()

# ================= PRODUCT ENTRY =================
if role == "user" and st.session_state.statement_id:
    stmt = supabase.table("sales_stock_statements")\
        .select("*")\
        .eq("id", st.session_state.statement_id)\
        .execute().data[0]

    if stmt["locked"]:
        st.error("This statement is locked by admin.")
        st.stop()

    products = st.session_state.products
    idx = st.session_state.product_index

    if idx >= len(products):
        st.success("All products completed.")
        st.stop()

    prod = products[idx]
    pid = prod["id"]

    st.subheader(prod["name"])

    existing = st.session_state.draft.get(pid)

    if existing:
        opening = st.number_input("Opening", value=existing["opening"], key=f"o_{pid}")
        purchase = st.number_input("Purchase", value=existing["purchase"], key=f"p_{pid}")
        issue = st.number_input("Issue", value=existing["issue"], key=f"i_{pid}")
        closing = st.number_input("Closing", value=existing["closing"], key=f"c_{pid}")
    else:
        last_close = get_last_closing(pid, stmt["stockist_id"], stmt["year"], stmt["month"])
        opening = st.number_input("Opening", value=last_close, key=f"o_{pid}")
        purchase = st.number_input("Purchase", value=0, key=f"p_{pid}")
        issue = st.number_input("Issue", value=0, key=f"i_{pid}")
        closing = st.number_input("Closing", value=0, key=f"c_{pid}")

    diff = opening + purchase - issue - closing
    st.info(f"Difference: {diff}")

    st.session_state.draft[pid] = {
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
                .update({"locked": True})\
                .eq("id", s["id"])\
                .execute()
            st.rerun()

        if s["locked"] and col[3].button("Unlock", key=f"u{s['id']}"):
            supabase.table("sales_stock_statements")\
                .update({"locked": False})\
                .eq("id", s["id"])\
                .execute()
            st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
