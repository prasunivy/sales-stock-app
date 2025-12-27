import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta

# ================= CONFIG =================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ================= SESSION =================
defaults = {
    "logged_in": False,
    "user": None,
    "nav": "Exception Dashboard",
    "edit_statement_id": None,
    "view_only": False
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ================= AUTH =================
def login(u, p):
    res = supabase.table("users") \
        .select("*") \
        .eq("username", u.strip()) \
        .eq("password", p.strip()) \
        .execute().data
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
    if st.sidebar.button("Exception Dashboard"):
        st.session_state.nav = "Exception Dashboard"
        st.session_state.edit_statement_id = None

    if st.sidebar.button("Lock Control"):
        st.session_state.nav = "Lock Control"
        st.session_state.edit_statement_id = None
else:
    st.sidebar.write("User flow unchanged")

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ============ ADMIN STATEMENT VIEW (PRIORITY) ============
# =========================================================
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

    st.header("🔍 Admin Statement Review")

    st.write(f"**Period:** {stmt['month']} {stmt['year']}")
    st.write(f"**Status:** {'Locked' if stmt['locked'] else 'Open'}")
    st.write("---")

    for p in products:
        if p["id"] not in item_map:
            continue
        i = item_map[p["id"]]

        st.subheader(p["name"])
        st.write(f"Opening: {i['opening']}")
        st.write(f"Purchase: {i['purchase']}")
        st.write(f"Issue: {i['issue']}")
        st.write(f"Closing: {i['closing']}")
        st.write(f"Difference: {i['difference']}")
        st.write("---")

    if st.button("⬅ Back to Dashboard"):
        st.session_state.edit_statement_id = None
        st.session_state.view_only = False
        st.rerun()

    st.stop()

# =========================================================
# ============ ADMIN EXCEPTION DASHBOARD ==================
# =========================================================
if role == "admin" and st.session_state.nav == "Exception Dashboard":
    st.header("🚨 Admin Exception Dashboard")

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}
    products = {p["id"]: p["name"] for p in supabase.table("products").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data

    today = datetime.utcnow()

    stmt_rows = []
    prod_rows = []
    months_set = set()

    # ---------- PRODUCT LEVEL ----------
    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        month_label = f"{stmt['month']} {stmt['year']}"
        months_set.add(month_label)

        def add_prod(ex):
            prod_rows.append({
                "Statement ID": stmt["id"],
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": i["issue"],
                "Closing": i["closing"],
                "Exception": ex
            })

        if i["issue"] == 0 and i["closing"] > 0:
            add_prod("Zero Issue, Stock Present")
        if i["issue"] > 0 and i["closing"] >= 2 * i["issue"]:
            add_prod("Closing ≥ 2× Issue")
        if i["difference"] != 0:
            add_prod("Stock Mismatch")

    # ---------- STATEMENT LEVEL ----------
    for s in stmts:
        created = datetime.fromisoformat(s["created_at"].replace("Z", ""))
        base = {
            "Statement ID": s["id"],
            "User": users.get(s["user_id"], "Unknown"),
            "Stockist": stockists.get(s["stockist_id"], "Unknown"),
            "Month": f"{s['month']} {s['year']}"
        }

        if s["status"] == "draft" and today - created > timedelta(days=3):
            stmt_rows.append({**base, "Exception": "Draft > 3 Days"})

        if s["status"] == "final" and not s["locked"]:
            stmt_rows.append({**base, "Exception": "Final but Not Locked"})

        if any(p["Statement ID"] == s["id"] for p in prod_rows):
            stmt_rows.append({**base, "Exception": "Product Exceptions"})

    # ---------- FILTERS ----------
    st.subheader("📄 Statement-wise Exceptions")
    stmt_filter = st.selectbox(
        "Filter by Exception",
        ["All", "Draft > 3 Days", "Final but Not Locked", "Product Exceptions"]
    )

    filtered_stmt = stmt_rows if stmt_filter == "All" else [
        r for r in stmt_rows if r["Exception"] == stmt_filter
    ]

    for idx, r in enumerate(filtered_stmt):
        c1, c2, c3, c4, c5 = st.columns([2,2,2,3,1])
        c1.write(r["User"])
        c2.write(r["Stockist"])
        c3.write(r["Month"])
        c4.write(r["Exception"])
        if c5.button("Open", key=f"stmt_{r['Statement ID']}_{idx}"):
            st.session_state.edit_statement_id = r["Statement ID"]
            st.rerun()

    st.write("---")

    st.subheader("📦 Product-level Exceptions")
    month_filter = st.selectbox(
        "Select Month",
        ["All"] + sorted(months_set, reverse=True)
    )

    filtered_prod = prod_rows if month_filter == "All" else [
        p for p in prod_rows if p["Month"] == month_filter
    ]

    for idx, r in enumerate(filtered_prod):
        c1, c2, c3, c4, c5, c6 = st.columns([2,2,2,2,2,1])
        c1.write(r["Product"])
        c2.write(r["Stockist"])
        c3.write(r["Month"])
        c4.write(r["Exception"])
        c5.write(f"Issue:{r['Issue']} / Close:{r['Closing']}")
        if c6.button("Open", key=f"prod_{r['Statement ID']}_{idx}"):
            st.session_state.edit_statement_id = r["Statement ID"]
            st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
