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

# ================= HELPERS =================
SEVERITY_RANK = {"High": 1, "Medium": 2, "Low": 3}

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
# ============ PHASE 10C.3 — SEVERITY DASHBOARD ============
# =========================================================
if role == "admin" and st.session_state.nav == "Exception Dashboard":
    st.header("🚨 Exception Dashboard (Severity Prioritised)")

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}
    products = {p["id"]: p["name"] for p in supabase.table("products").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data

    today = datetime.utcnow()
    stmt_rows, prod_rows, months = [], [], set()

    # ---------------- PRODUCT LEVEL ----------------
    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        month_label = f"{stmt['month']} {stmt['year']}"
        months.add(month_label)

        def add_prod(ex, sev):
            prod_rows.append({
                "Severity": sev,
                "SeverityRank": SEVERITY_RANK[sev],
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": i["issue"],
                "Closing": i["closing"],
                "Exception": ex
            })

        if i["difference"] != 0:
            add_prod("Stock Mismatch", "High")
        elif i["issue"] == 0 and i["closing"] > 0:
            add_prod("Zero Issue, Stock Present", "Medium")
        elif i["issue"] > 0 and i["closing"] >= 2 * i["issue"]:
            add_prod("Closing >= 2x Issue", "Low")

    prod_rows.sort(key=lambda x: x["SeverityRank"])

    # ---------------- STATEMENT LEVEL ----------------
    for s in stmts:
        created = datetime.fromisoformat(s["created_at"].replace("Z", ""))
        base = {
            "User": users.get(s["user_id"], "Unknown"),
            "Stockist": stockists.get(s["stockist_id"], "Unknown"),
            "Month": f"{s['month']} {s['year']}"
        }

        if s["status"] == "draft" and today - created > timedelta(days=3):
            stmt_rows.append({**base, "Exception": "Draft > 3 Days", "Severity": "High", "SeverityRank": 1})

        if s["status"] == "final" and not s["locked"]:
            stmt_rows.append({**base, "Exception": "Final but Not Locked", "Severity": "Medium", "SeverityRank": 2})

        if any(p["Month"] == base["Month"] for p in prod_rows):
            stmt_rows.append({**base, "Exception": "Product Exceptions", "Severity": "Low", "SeverityRank": 3})

    stmt_rows.sort(key=lambda x: x["SeverityRank"])

    # ================= STATEMENT VIEW =================
    st.subheader("📄 Statement Exceptions (Prioritised)")
    st.dataframe(stmt_rows, use_container_width=True)

    # ================= PRODUCT VIEW =================
    st.subheader("📦 Product Exceptions (Prioritised)")
    month_filter = st.selectbox("Filter by Month", ["All"] + sorted(months, reverse=True))
    filtered_prod = prod_rows if month_filter == "All" else [p for p in prod_rows if p["Month"] == month_filter]
    st.dataframe(filtered_prod, use_container_width=True)

    # ================= EXPORT =================
    st.subheader("⬇ Export")

    def export_pdf(rows, title, fname):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, safe_pdf_text(title), ln=True)
        for r in rows:
            for k, v in r.items():
                if k not in ["SeverityRank"]:
                    pdf.cell(0, 8, f"{safe_pdf_text(k)}: {safe_pdf_text(v)}", ln=True)
            pdf.cell(0, 8, "-" * 40, ln=True)
        return pdf.output(dest="S").encode("latin-1")

    if stmt_rows:
        st.download_button(
            "Download Statement Exceptions PDF",
            export_pdf(stmt_rows, "STATEMENT EXCEPTIONS", "stmt.pdf"),
            "statement_exceptions.pdf",
            "application/pdf"
        )

    if filtered_prod:
        st.download_button(
            "Download Product Exceptions PDF",
            export_pdf(filtered_prod, "PRODUCT EXCEPTIONS", "prod.pdf"),
            "product_exceptions.pdf",
            "application/pdf"
        )

st.write("---")
st.write("© Ivy Pharmaceuticals")
