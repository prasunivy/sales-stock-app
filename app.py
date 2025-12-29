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

SEVERITY = {
    "High": "🔴 HIGH",
    "Medium": "🟠 MEDIUM",
    "Low": "🟡 LOW"
}

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Home",
    "statement_id": None,
    "product_index": 0,
    "view_stmt_id": None,
    "edit_stmt_id": None,
}.items():
    st.session_state.setdefault(k, v)

# ================= HELPERS =================
def login(username, password):
    res = supabase.table("users") \
        .select("*") \
        .eq("username", username.strip()) \
        .eq("password", password.strip()) \
        .execute().data
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
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

role = st.session_state.user["role"]
uid = st.session_state.user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role == "admin":
    if st.sidebar.button("📝 Data Entry"):
        st.session_state.nav = "Home"
    if st.sidebar.button("📊 Exception Dashboard"):
        st.session_state.nav = "Exceptions"
    if st.sidebar.button("🔐 Lock Control"):
        st.session_state.nav = "Lock"
    if st.sidebar.button("📈 Matrix Dashboards"):
        st.session_state.nav = "Matrix"

if role == "user":
    if st.sidebar.button("📝 New Statement"):
        st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= USER — DATA ENTRY =====================
# =========================================================
if role == "user" and st.session_state.nav == "New Statement":
    st.header("📝 New Sales & Stock Statement")

    mappings = supabase.table("user_stockist") \
        .select("stockist_id") \
        .eq("user_id", uid) \
        .execute().data

    if not mappings:
        st.warning("No stockist allocated. Contact admin.")
        st.stop()

    stockist_ids = [m["stockist_id"] for m in mappings]
    stockists = supabase.table("stockists").select("*").in_("id", stockist_ids).execute().data

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

# ================= PRODUCT ENTRY =================
if role == "user" and st.session_state.statement_id:
    products = supabase.table("products").select("*").order("name").execute().data
    prod = products[st.session_state.product_index]

    st.subheader(f"📦 {prod['name']}")

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
        if st.session_state.product_index >= len(products):
            supabase.table("sales_stock_statements") \
                .update({"status": "final"}) \
                .eq("id", st.session_state.statement_id).execute()
            st.success("Statement submitted")
            st.session_state.statement_id = None
        st.rerun()

# =========================================================
# ================= ADMIN — MATRIX DASHBOARDS =============
# =========================================================
if role == "admin" and st.session_state.nav == "Matrix":
    st.header("📈 Matrix Dashboards")

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data
    products = supabase.table("products").select("*").execute().data

    # -------- Matrix 1 --------
    st.subheader("📊 Month × Product")

    year_sel = st.selectbox("Year", sorted({s["year"] for s in stmts}, reverse=True))
    month_sel = st.selectbox("Month", MONTH_ORDER)

    matrix1 = []
    for p in products:
        p_items = [
            i for i in items
            if i["product_id"] == p["id"]
            and any(
                s["id"] == i["statement_id"]
                and s["year"] == year_sel
                and s["month"] == month_sel
                for s in stmts
            )
        ]
        if p_items:
            matrix1.append({
                "Product": p["name"],
                "Opening": sum(i["opening"] for i in p_items),
                "Purchase": sum(i["purchase"] for i in p_items),
                "Issue": sum(i["issue"] for i in p_items),
                "Closing": sum(i["closing"] for i in p_items),
                "Difference": sum(i["difference"] for i in p_items)
            })

    if matrix1:
        df1 = pd.DataFrame(matrix1)
        st.dataframe(df1, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ CSV", df1.to_csv(index=False),
                               f"matrix1_{month_sel}_{year_sel}.csv")
        with c2:
            st.download_button("⬇️ PDF",
                               generate_pdf("Matrix 1 — Month × Product",
                                            f"{month_sel} {year_sel}", df1),
                               f"matrix1_{month_sel}_{year_sel}.pdf")
    else:
        st.info("No data available.")

    st.divider()

    # -------- Matrix 2 --------
    st.subheader("📈 Product × Month")

    prod_sel = st.selectbox("Product", products, format_func=lambda x: x["name"])
    year_sel2 = st.selectbox("Year ", sorted({s["year"] for s in stmts}, reverse=True))

    matrix2 = []
    for m in MONTH_ORDER:
        m_items = [
            i for i in items
            if i["product_id"] == prod_sel["id"]
            and any(
                s["id"] == i["statement_id"]
                and s["year"] == year_sel2
                and s["month"] == m
                for s in stmts
            )
        ]
        if m_items:
            matrix2.append({
                "Month": m,
                "Opening": sum(i["opening"] for i in m_items),
                "Purchase": sum(i["purchase"] for i in m_items),
                "Issue": sum(i["issue"] for i in m_items),
                "Closing": sum(i["closing"] for i in m_items),
                "Difference": sum(i["difference"] for i in m_items)
            })

    if matrix2:
        df2 = pd.DataFrame(matrix2)
        st.dataframe(df2, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ CSV", df2.to_csv(index=False),
                               f"matrix2_{prod_sel['name']}_{year_sel2}.csv")
        with c2:
            st.download_button("⬇️ PDF",
                               generate_pdf("Matrix 2 — Product × Month",
                                            f"{prod_sel['name']} ({year_sel2})", df2),
                               f"matrix2_{prod_sel['name']}_{year_sel2}.pdf")
    else:
        st.info("No data available.")

st.write("---")
st.write("© Ivy Pharmaceuticals")
