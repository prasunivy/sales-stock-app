import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
from fpdf import FPDF

# ================= CONFIG =================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTH_ORDER = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ================= SESSION =================
for k in [
    "logged_in", "user", "nav",
    "statement_id", "product_index"
]:
    st.session_state.setdefault(k, None)

# ================= HELPERS =================
def safe_select(table, **filters):
    try:
        q = supabase.table(table).select("*")
        for k, v in filters.items():
            q = q.eq(k, v)
        return q.execute().data or []
    except Exception:
        return []

def login(username, password):
    res = safe_select(
        "users",
        username=username.strip(),
        password=password.strip()
    )
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.session_state.nav = "Home"
        st.rerun()
    st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

def generate_pdf(title, subtitle, df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Ivy Pharmaceuticals", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, title, ln=True)
    pdf.cell(0, 8, subtitle, ln=True)
    pdf.ln(4)

    pdf.set_font("Arial", "B", 9)
    for col in df.columns:
        pdf.cell(30, 8, col[:10], border=1)
    pdf.ln()

    pdf.set_font("Arial", "", 9)
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(30, 8, str(int(val)) if isinstance(val, (int, float)) else str(val), border=1)
        pdf.ln()

    return pdf.output(dest="S").encode("latin-1", "ignore")

# ================= LOGIN =================
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u, p)
    st.stop()

user = st.session_state.user
role = user["role"]
uid = user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role == "admin":
    if st.sidebar.button("👤 Users"): st.session_state.nav = "Users"
    if st.sidebar.button("📦 Products"): st.session_state.nav = "Products"
    if st.sidebar.button("🏪 Stockists"): st.session_state.nav = "Stockists"
    if st.sidebar.button("🔗 Allocate Stockists"): st.session_state.nav = "Allocate"
    if st.sidebar.button("📈 Matrix Dashboards"): st.session_state.nav = "Matrix"

if role == "user":
    if st.sidebar.button("📝 New Statement"):
        st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — USERS =========================
# =========================================================
if role == "admin" and st.session_state.nav == "Users":
    st.header("👤 Manage Users")
    uname = st.text_input("Username")
    pwd = st.text_input("Password")
    r = st.selectbox("Role", ["user", "admin"])
    if st.button("Add User"):
        supabase.table("users").insert({
            "username": uname, "password": pwd, "role": r
        }).execute()
        st.success("User added")

    for u in safe_select("users"):
        st.write(f"{u['username']} ({u['role']})")

# =========================================================
# ================= ADMIN — PRODUCTS ======================
# =========================================================
if role == "admin" and st.session_state.nav == "Products":
    st.header("📦 Products")
    p = st.text_input("Product name")
    if st.button("Add Product"):
        supabase.table("products").insert({"name": p}).execute()
        st.success("Added")

    for p in safe_select("products"):
        st.write(p["name"])

# =========================================================
# ================= ADMIN — STOCKISTS =====================
# =========================================================
if role == "admin" and st.session_state.nav == "Stockists":
    st.header("🏪 Stockists")
    s = st.text_input("Stockist name")
    if st.button("Add Stockist"):
        supabase.table("stockists").insert({"name": s}).execute()
        st.success("Added")

    for s in safe_select("stockists"):
        st.write(s["name"])

# =========================================================
# ============ ADMIN — ALLOCATE STOCKISTS =================
# =========================================================
if role == "admin" and st.session_state.nav == "Allocate":
    users = safe_select("users")
    stockists = safe_select("stockists")

    u = st.selectbox("User", users, format_func=lambda x: x["username"])
    s = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])

    if st.button("Allocate"):
        supabase.table("user_stockist").insert({
            "user_id": u["id"],
            "stockist_id": s["id"]
        }).execute()
        st.success("Allocated")

# =========================================================
# ================= USER — NEW STATEMENT ==================
# =========================================================
if role == "user" and st.session_state.nav == "New Statement":
    st.header("📝 New Statement")

    mappings = safe_select("user_stockist", user_id=uid)
    if not mappings:
        st.warning("No stockist allocated. Contact admin.")
        st.stop()

    stockist_ids = [m["stockist_id"] for m in mappings]
    stockists = [s for s in safe_select("stockists") if s["id"] in stockist_ids]

    sel_stockist = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])
    month = st.selectbox("Month", MONTH_ORDER)
    year = st.number_input("Year", value=datetime.now().year)

    if st.button("Create Statement"):
        res = supabase.table("sales_stock_statements").insert({
            "user_id": uid,
            "stockist_id": sel_stockist["id"],
            "month": month,
            "year": int(year),
            "status": "draft",
            "locked": False
        }).execute()

        st.session_state.statement_id = res.data[0]["id"]
        st.session_state.product_index = 0
        st.rerun()

# =========================================================
# ================= PRODUCT ENTRY =========================
# =========================================================
if role == "user" and st.session_state.statement_id:
    products = safe_select("products")
    idx = st.session_state.product_index

    if idx >= len(products):
        supabase.table("sales_stock_statements") \
            .update({"status": "final"}) \
            .eq("id", st.session_state.statement_id).execute()
        st.success("Statement submitted")
        st.session_state.statement_id = None
        st.stop()

    prod = products[idx]
    st.subheader(prod["name"])

    opening = st.number_input("Opening", 0, step=1)
    purchase = st.number_input("Purchase", 0, step=1)
    issue = st.number_input("Issue", 0, step=1)
    closing = st.number_input("Closing", 0, step=1)

    diff = opening + purchase - issue - closing
    st.write(f"Difference: {diff}")

    if st.button("Save & Next"):
        supabase.table("sales_stock_items").insert({
            "statement_id": st.session_state.statement_id,
            "product_id": prod["id"],
            "opening": opening,
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "difference": diff
        }).execute()
        st.session_state.product_index += 1
        st.rerun()

# =========================================================
# ================= ADMIN — MATRIX ========================
# =========================================================
if role == "admin" and st.session_state.nav == "Matrix":
    st.header("📈 Matrix Dashboard")

    stmts = safe_select("sales_stock_statements")
    items = safe_select("sales_stock_items")
    products = safe_select("products")

    if not stmts:
        st.info("No data yet.")
        st.stop()

    year = st.selectbox("Year", sorted({s["year"] for s in stmts}, reverse=True))
    month = st.selectbox("Month", MONTH_ORDER)

    rows = []
    for p in products:
        p_items = [
            i for i in items
            if i["product_id"] == p["id"]
            and any(
                s["id"] == i["statement_id"]
                and s["year"] == year
                and s["month"] == month
                for s in stmts
            )
        ]
        if p_items:
            rows.append({
                "Product": p["name"],
                "Opening": sum(i["opening"] for i in p_items),
                "Purchase": sum(i["purchase"] for i in p_items),
                "Issue": sum(i["issue"] for i in p_items),
                "Closing": sum(i["closing"] for i in p_items),
                "Difference": sum(i["difference"] for i in p_items)
            })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df)
        st.download_button("⬇️ CSV", df.to_csv(index=False),
                           f"matrix_{month}_{year}.csv")
        st.download_button("⬇️ PDF",
                           generate_pdf("Matrix", f"{month} {year}", df),
                           f"matrix_{month}_{year}.pdf")
    else:
        st.info("No data for selected period.")

st.write("---")
st.write("© Ivy Pharmaceuticals")
