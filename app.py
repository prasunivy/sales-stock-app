import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import csv
import io

# ================= CONFIG =================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= SESSION =================
defaults = {
    "logged_in": False,
    "user": None,
    "nav": "Exception Dashboard",
    "edit_statement_id": None
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

if st.sidebar.button("Logout"):
    logout()

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
        created = datetime.fromisoformat(s["created_at"].replace("Z",""))
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

    # ================= STATEMENT FILTER =================
    st.subheader("📄 Statement-wise Exceptions")
    stmt_filter = st.selectbox(
        "Filter by Exception",
        ["All", "Draft > 3 Days", "Final but Not Locked", "Product Exceptions"]
    )

    filtered_stmt = stmt_rows if stmt_filter == "All" else [
        r for r in stmt_rows if r["Exception"] == stmt_filter
    ]

    if filtered_stmt:
        st.dataframe(filtered_stmt, use_container_width=True)

        # -------- CSV EXPORT --------
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=filtered_stmt[0].keys())
        writer.writeheader()
        writer.writerows(filtered_stmt)

        st.download_button(
            "⬇ Download Statement Exceptions (CSV)",
            csv_buf.getvalue(),
            file_name="statement_exceptions.csv",
            mime="text/csv"
        )

        # -------- PDF EXPORT (TEXT) --------
        pdf_text = "STATEMENT EXCEPTIONS REPORT\n\n"
        for r in filtered_stmt:
            for k, v in r.items():
                pdf_text += f"{k}: {v}\n"
            pdf_text += "-" * 40 + "\n"

        st.download_button(
            "⬇ Download Statement Exceptions (PDF)",
            pdf_text,
            file_name="statement_exceptions.pdf",
            mime="application/pdf"
        )

    st.write("---")

    # ================= PRODUCT FILTER =================
    st.subheader("📦 Product-level Exceptions")
    month_filter = st.selectbox(
        "Select Month",
        ["All"] + sorted(months_set, reverse=True)
    )

    filtered_prod = prod_rows if month_filter == "All" else [
        p for p in prod_rows if p["Month"] == month_filter
    ]

    if filtered_prod:
        st.dataframe(filtered_prod, use_container_width=True)

        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=filtered_prod[0].keys())
        writer.writeheader()
        writer.writerows(filtered_prod)

        st.download_button(
            "⬇ Download Product Exceptions (CSV)",
            csv_buf.getvalue(),
            file_name="product_exceptions.csv",
            mime="text/csv"
        )

        pdf_text = "PRODUCT EXCEPTIONS REPORT\n\n"
        for r in filtered_prod:
            for k, v in r.items():
                pdf_text += f"{k}: {v}\n"
            pdf_text += "-" * 40 + "\n"

        st.download_button(
            "⬇ Download Product Exceptions (PDF)",
            pdf_text,
            file_name="product_exceptions.pdf",
            mime="application/pdf"
        )

st.write("---")
st.write("© Ivy Pharmaceuticals")
