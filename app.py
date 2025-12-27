import streamlit as st
from supabase import create_client
from datetime import date, datetime, timedelta

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
    "view_only": False
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
    navs = ["Lock Control", "Exception Dashboard"]
else:
    navs = ["Create / Resume"]

for n in navs:
    if st.sidebar.button(n):
        st.session_state.nav = n
        st.session_state.edit_statement_id = None

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN EXCEPTION DASHBOARD ==============
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

    # -------- PRODUCT LEVEL --------
    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        month_label = f"{stmt['month']} {stmt['year']}"

        issue = i["issue"]
        closing = i["closing"]
        diff = i["difference"]

        def add_prod(ex):
            prod_rows.append({
                "Statement ID": stmt["id"],
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": issue,
                "Closing": closing,
                "Exception": ex
            })

        if issue == 0 and closing > 0:
            add_prod("Zero Issue, Stock Present")
        if issue > 0 and closing >= 2 * issue:
            add_prod("Closing ≥ 2× Issue")
        if diff != 0:
            add_prod("Stock Mismatch")

    # -------- STATEMENT LEVEL --------
    for s in stmts:
        created = datetime.fromisoformat(s["created_at"].replace("Z",""))
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

    # -------- STATEMENT TABLE --------
    st.subheader("📄 Statement-wise Exceptions")

    for idx, row in enumerate(stmt_rows):
        c1, c2, c3, c4, c5 = st.columns([2,2,2,3,1])
        c1.write(row["User"])
        c2.write(row["Stockist"])
        c3.write(row["Month"])
        c4.write(row["Exception"])
        if c5.button("Open", key=f"open_stmt_{row['Statement ID']}_{idx}"):
            st.session_state.edit_statement_id = row["Statement ID"]
            st.session_state.view_only = True
            st.session_state.nav = "Lock Control"
            st.rerun()

    st.write("---")

    # -------- PRODUCT TABLE --------
    st.subheader("📦 Product-level Exceptions")

    for idx, row in enumerate(prod_rows):
        c1, c2, c3, c4, c5, c6 = st.columns([2,2,2,2,2,1])
        c1.write(row["Product"])
        c2.write(row["Stockist"])
        c3.write(row["Month"])
        c4.write(row["Exception"])
        c5.write(f"Issue:{row['Issue']} / Close:{row['Closing']}")
        if c6.button("Open", key=f"open_prod_{row['Statement ID']}_{idx}"):
            st.session_state.edit_statement_id = row["Statement ID"]
            st.session_state.view_only = True
            st.session_state.nav = "Lock Control"
            st.rerun()

# =========================================================
# ================= ADMIN VIEW =============================
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
    st.write(f"**Locked:** {'Yes' if stmt['locked'] else 'No'}")
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

    if st.button("Back"):
        st.session_state.edit_statement_id = None
        st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
