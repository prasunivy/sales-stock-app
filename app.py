import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import csv, io
from fpdf import FPDF

# ================= CONFIG =================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= HELPERS =================
def safe_pdf_text(text):
    if text is None:
        return ""
    return (
        str(text)
        .replace("≥", ">=")
        .replace("×", "x")
        .replace("–", "-")
        .replace("—", "-")
        .encode("latin-1", "ignore")
        .decode("latin-1")
    )

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Exception Dashboard",
    "refresh": 0
}.items():
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
    if st.sidebar.button("Lock Control"):
        st.session_state.nav = "Lock Control"
if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= LOCK CONTROL (FIXED) ==================
# =========================================================
if role == "admin" and st.session_state.nav == "Lock Control":
    st.header("🔐 Lock Control")

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute().data

    for s in stmts:
        with st.container(border=True):
            st.write(f"**User:** {users.get(s['user_id'], 'Unknown')}")
            st.write(f"**Stockist:** {stockists.get(s['stockist_id'], 'Unknown')}")
            st.write(f"**Period:** {s['month']} {s['year']}")
            st.write(f"**Status:** {'Locked' if s['locked'] else 'Open'}")

            if st.button(
                "Unlock" if s["locked"] else "Lock",
                key=f"lock_{s['id']}_{st.session_state.refresh}"
            ):
                supabase.table("sales_stock_statements") \
                    .update({"locked": not s["locked"]}) \
                    .eq("id", s["id"]) \
                    .execute()

                # Force clean refresh
                st.session_state.refresh += 1
                st.success("Lock status updated")
                st.rerun()

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
    months = set()

    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        month_label = f"{stmt['month']} {stmt['year']}"
        months.add(month_label)

        def add_prod(ex):
            prod_rows.append({
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
            add_prod("Closing >= 2x Issue")
        if i["difference"] != 0:
            add_prod("Stock Mismatch")

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

        if any(p["Month"] == base["Month"] for p in prod_rows):
            stmt_rows.append({**base, "Exception": "Product Exceptions"})

    st.subheader("📄 Statement-wise Exceptions")
    st.dataframe(stmt_rows, use_container_width=True)

    st.subheader("📦 Product-level Exceptions")
    st.dataframe(prod_rows, use_container_width=True)

st.write("---")
st.write("© Ivy Pharmaceuticals")
