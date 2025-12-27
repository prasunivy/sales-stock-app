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
    available_months = set()

    # ---------------- PRODUCT LEVEL ----------------
    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        month_label = f"{stmt['month']} {stmt['year']}"
        available_months.add(month_label)

        issue = i["issue"]
        closing = i["closing"]
        diff = i["difference"]

        if issue == 0 and closing > 0:
            prod_rows.append({
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": issue,
                "Closing": closing,
                "Exception": "Zero Issue, Stock Present"
            })

        if issue > 0 and closing >= 2 * issue:
            prod_rows.append({
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": issue,
                "Closing": closing,
                "Exception": "Closing ≥ 2× Issue"
            })

        if diff != 0:
            prod_rows.append({
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": issue,
                "Closing": closing,
                "Exception": "Stock Mismatch"
            })

    # ---------------- STATEMENT LEVEL ----------------
    for s in stmts:
        created = datetime.fromisoformat(s["created_at"].replace("Z", ""))
        base = {
            "User": users.get(s["user_id"], "Unknown"),
            "Stockist": stockists.get(s["stockist_id"], "Unknown"),
            "Month": f"{s['month']} {s['year']}"
        }

        if s["status"] == "draft" and today - created > timedelta(days=3):
            stmt_rows.append({**base, "Exception": "Draft > 3 Days"})

        if s["status"] == "final" and not s["locked"]:
            stmt_rows.append({**base, "Exception": "Final but Not Locked"})

        prod_ex_count = sum(1 for p in prod_rows if p["Month"] == base["Month"])
        if prod_ex_count > 0:
            stmt_rows.append({**base, "Exception": "Product Exceptions"})

    # ---------------- SUMMARY ----------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Statements", len(stmts))
    c2.metric("Statement Exceptions", len(stmt_rows))
    c3.metric("Product Exceptions", len(prod_rows))

    st.write("---")

    # ================= STATEMENT FILTER =================
    st.subheader("📄 Statement-wise Exceptions")
    stmt_filter = st.selectbox(
        "Filter by Exception",
        ["All", "Draft > 3 Days", "Final but Not Locked", "Product Exceptions"]
    )

    filtered_stmt = stmt_rows if stmt_filter == "All" else [
        s for s in stmt_rows if s["Exception"] == stmt_filter
    ]

    if filtered_stmt:
        st.dataframe(filtered_stmt, use_container_width=True)
    else:
        st.info("No matching statement exceptions")

    st.write("---")

    # ================= PRODUCT FILTER =================
    st.subheader("📦 Product-level Exceptions")
    month_filter = st.selectbox(
        "Select Month",
        ["All"] + sorted(available_months, reverse=True)
    )

    filtered_prod = prod_rows if month_filter == "All" else [
        p for p in prod_rows if p["Month"] == month_filter
    ]

    if filtered_prod:
        st.dataframe(filtered_prod, use_container_width=True)
    else:
        st.info("No matching product exceptions")

st.write("---")
st.write("© Ivy Pharmaceuticals")
