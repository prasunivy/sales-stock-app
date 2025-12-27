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
    stmt_exceptions = []
    product_exceptions = []

    # -------- PRODUCT LEVEL EXCEPTIONS --------
    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        issue = i["issue"]
        closing = i["closing"]
        diff = i["difference"]

        exception_types = []

        if issue == 0 and closing > 0:
            exception_types.append("Zero Issue, Stock Present")

        if issue > 0 and closing >= 2 * issue:
            exception_types.append("Closing ≥ 2× Issue")

        if diff != 0:
            exception_types.append("Stock Mismatch")

        for ex in exception_types:
            product_exceptions.append({
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Month": f"{stmt['month']} {stmt['year']}",
                "Issue": issue,
                "Closing": closing,
                "Exception": ex
            })

    # -------- STATEMENT LEVEL EXCEPTIONS --------
    for s in stmts:
        created = datetime.fromisoformat(s["created_at"].replace("Z",""))
        ex_count = sum(
            1 for i in items if i["statement_id"] == s["id"]
            and (
                (i["issue"] == 0 and i["closing"] > 0)
                or (i["issue"] > 0 and i["closing"] >= 2 * i["issue"])
                or i["difference"] != 0
            )
        )

        if ex_count > 0:
            stmt_exceptions.append({
                "User": users.get(s["user_id"], "Unknown"),
                "Stockist": stockists.get(s["stockist_id"], "Unknown"),
                "Month": f"{s['month']} {s['year']}",
                "Exceptions": ex_count
            })

        if s["status"] == "draft" and today - created > timedelta(days=3):
            stmt_exceptions.append({
                "User": users.get(s["user_id"], "Unknown"),
                "Stockist": stockists.get(s["stockist_id"], "Unknown"),
                "Month": f"{s['month']} {s['year']}",
                "Exceptions": "Draft > 3 Days"
            })

        if s["status"] == "final" and not s["locked"]:
            stmt_exceptions.append({
                "User": users.get(s["user_id"], "Unknown"),
                "Stockist": stockists.get(s["stockist_id"], "Unknown"),
                "Month": f"{s['month']} {s['year']}",
                "Exceptions": "Final but Not Locked"
            })

    # -------- SUMMARY --------
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Statements", len(stmts))
    c2.metric("Statements with Exceptions", len(stmt_exceptions))
    c3.metric("Product Exceptions", len(product_exceptions))

    st.write("---")

    st.subheader("📄 Statement-wise Exceptions")
    if stmt_exceptions:
        st.dataframe(stmt_exceptions, use_container_width=True)
    else:
        st.success("No statement-level exceptions found")

    st.write("---")

    st.subheader("📦 Product-level Exceptions")
    if product_exceptions:
        st.dataframe(product_exceptions, use_container_width=True)
    else:
        st.success("No product-level exceptions found")

st.write("---")
st.write("© Ivy Pharmaceuticals")
