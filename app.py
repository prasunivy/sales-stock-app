import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import csv, io
from fpdf import FPDF

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Exception Dashboard",
}.items():
    st.session_state.setdefault(k, v)

# ================= AUTH =================
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
if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ============ ADMIN EXCEPTION DASHBOARD ==================
# =========================================================
if role == "admin":
    st.header("🚨 Admin Exception Dashboard")

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}
    products = {p["id"]: p["name"] for p in supabase.table("products").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data

    today = datetime.utcnow()
    stmt_rows, prod_rows, months = [], [], set()

    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        month = f"{stmt['month']} {stmt['year']}"
        months.add(month)

        if i["issue"] == 0 and i["closing"] > 0:
            prod_rows.append({
                "Month": month,
                "Product": products[i["product_id"]],
                "Stockist": stockists[stmt["stockist_id"]],
                "Issue": i["issue"],
                "Closing": i["closing"],
                "Exception": "Zero Issue, Stock Present"
            })

    # ---------------- STATEMENT FILTER ----------------
    st.subheader("📄 Statement Exceptions")
    if stmt_rows:
        st.dataframe(stmt_rows)

    # ---------------- PRODUCT FILTER ----------------
    st.subheader("📦 Product Exceptions")
    if prod_rows:
        st.dataframe(prod_rows)

        # ---------------- CSV ----------------
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=prod_rows[0].keys())
        writer.writeheader()
        writer.writerows(prod_rows)

        st.download_button(
            "⬇ Download CSV",
            csv_buf.getvalue(),
            "product_exceptions.csv",
            "text/csv"
        )

        # ---------------- REAL PDF ----------------
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, "PRODUCT EXCEPTION REPORT", ln=True)

        for r in prod_rows:
            for k, v in r.items():
                pdf.cell(0, 8, f"{k}: {v}", ln=True)
            pdf.cell(0, 8, "-" * 40, ln=True)

        pdf_bytes = pdf.output(dest="S").encode("latin-1")

        st.download_button(
            "⬇ Download PDF",
            pdf_bytes,
            "product_exceptions.pdf",
            "application/pdf"
        )

st.write("---")
st.write("© Ivy Pharmaceuticals")
