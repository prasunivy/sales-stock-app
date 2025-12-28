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

# ================= CONSTANTS =================
SEVERITY_RANK = {"High": 1, "Medium": 2, "Low": 3}

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
    "edit_statement_id": None,
    "refresh": 0
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
    if st.sidebar.button("Lock Control"):
        st.session_state.nav = "Lock Control"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= LOCK CONTROL ==========================
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

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("Edit", key=f"edit_{s['id']}_{st.session_state.refresh}", disabled=s["locked"]):
                    st.session_state.edit_statement_id = s["id"]
                    st.rerun()

            with c2:
                if st.button("Delete", key=f"del_{s['id']}_{st.session_state.refresh}", disabled=s["locked"]):
                    supabase.table("sales_stock_items").delete().eq("statement_id", s["id"]).execute()
                    supabase.table("sales_stock_statements").delete().eq("id", s["id"]).execute()
                    st.session_state.refresh += 1
                    st.success("Statement deleted")
                    st.rerun()

            with c3:
                if st.button("Unlock" if s["locked"] else "Lock", key=f"lock_{s['id']}_{st.session_state.refresh}"):
                    supabase.table("sales_stock_statements") \
                        .update({"locked": not s["locked"]}) \
                        .eq("id", s["id"]) \
                        .execute()
                    st.session_state.refresh += 1
                    st.rerun()

# =========================================================
# ============ EXCEPTION DASHBOARD (10C.3 FIXED) ==========
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

        if i["difference"] != 0:
            prod_rows.append({
                "Severity": "High", "SeverityRank": 1,
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": i["issue"],
                "Closing": i["closing"],
                "Exception": "Stock Mismatch"
            })
        elif i["issue"] == 0 and i["closing"] > 0:
            prod_rows.append({
                "Severity": "Medium", "SeverityRank": 2,
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": i["issue"],
                "Closing": i["closing"],
                "Exception": "Zero Issue, Stock Present"
            })
        elif i["issue"] > 0 and i["closing"] >= 2 * i["issue"]:
            prod_rows.append({
                "Severity": "Low", "SeverityRank": 3,
                "Month": month_label,
                "Product": products.get(i["product_id"], "Unknown"),
                "Stockist": stockists.get(stmt["stockist_id"], "Unknown"),
                "Issue": i["issue"],
                "Closing": i["closing"],
                "Exception": "Closing >= 2x Issue"
            })

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
            stmt_rows.append({**base, "Severity": "High", "SeverityRank": 1, "Exception": "Draft > 3 Days"})

        if s["status"] == "final" and not s["locked"]:
            stmt_rows.append({**base, "Severity": "Medium", "SeverityRank": 2, "Exception": "Final but Not Locked"})

        if any(p["Month"] == base["Month"] for p in prod_rows):
            stmt_rows.append({**base, "Severity": "Low", "SeverityRank": 3, "Exception": "Product Exceptions"})

    stmt_rows.sort(key=lambda x: x["SeverityRank"])

    # ---------------- STATEMENT VIEW ----------------
    st.subheader("📄 Statement Exceptions")
    st.dataframe(stmt_rows, use_container_width=True)

    if stmt_rows:
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=stmt_rows[0].keys())
        writer.writeheader()
        writer.writerows(stmt_rows)
        st.download_button("⬇ Download Statement CSV", csv_buf.getvalue(), "statement_exceptions.csv", "text/csv")

    # ---------------- PRODUCT VIEW ----------------
    st.subheader("📦 Product Exceptions")
    month_filter = st.selectbox("Filter by Month", ["All"] + sorted(months, reverse=True))
    filtered_prod = prod_rows if month_filter == "All" else [p for p in prod_rows if p["Month"] == month_filter]
    st.dataframe(filtered_prod, use_container_width=True)

    if filtered_prod:
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=filtered_prod[0].keys())
        writer.writeheader()
        writer.writerows(filtered_prod)
        st.download_button("⬇ Download Product CSV", csv_buf.getvalue(), "product_exceptions.csv", "text/csv")

    # ---------------- PDF EXPORT ----------------
    def export_pdf(rows, title):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, safe_pdf_text(title), ln=True)
        for r in rows:
            for k, v in r.items():
                if k != "SeverityRank":
                    pdf.cell(0, 8, f"{safe_pdf_text(k)}: {safe_pdf_text(v)}", ln=True)
            pdf.cell(0, 8, "-" * 40, ln=True)
        return pdf.output(dest="S").encode("latin-1")

    if stmt_rows:
        st.download_button(
            "⬇ Download Statement PDF",
            export_pdf(stmt_rows, "STATEMENT EXCEPTIONS"),
            "statement_exceptions.pdf",
            "application/pdf"
        )

    if filtered_prod:
        st.download_button(
            "⬇ Download Product PDF",
            export_pdf(filtered_prod, "PRODUCT EXCEPTIONS"),
            "product_exceptions.pdf",
            "application/pdf"
        )

st.write("---")
st.write("© Ivy Pharmaceuticals")
