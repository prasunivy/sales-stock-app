import streamlit as st
from supabase import create_client
from datetime import date
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTH_ORDER = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12
}

# ================= SESSION =================
session_defaults = {
    "logged_in": False,
    "user": None,
    "nav": "home",
    "statement_id": None,
    "selected_stockist": None,
    "from_date": None,
    "to_date": None,
    "year": None,
    "month": None,
    "product_index": 0,
    "products_cache": [],
}

for k,v in session_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ================= HELPERS =================
def login(username, password):
    res = supabase.table("users").select("*")\
        .eq("username", username.strip())\
        .eq("password", password.strip()).execute()

    if res.data:
        st.session_state.logged_in = True
        st.session_state.user = res.data[0]
        st.rerun()
    else:
        st.error("Invalid credentials")


def logout():
    st.session_state.clear()
    for k,v in session_defaults.items():
        st.session_state[k] = v
    st.rerun()


def generate_pdf(text):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = 750
    for line in text.split("\n"):
        c.drawString(40,y,line)
        y -= 15
        if y <= 40:
            c.showPage()
            y = 750
    c.save()
    buffer.seek(0)
    return buffer


# ================= UI START =================
st.title("Ivy Pharmaceuticals — Sales & Stock App")
# ================= LOGIN =================
if not st.session_state.logged_in:
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login(username, password)
    st.stop()


# ================= SIDEBAR NAVIGATION =================
role = st.session_state.user["role"]

st.sidebar.title("Navigation")

if st.sidebar.button("🏠 Home"):
    st.session_state.nav = "home"

if role == "admin":
    if st.sidebar.button("⚙️ Manage Database"):
        st.session_state.nav = "manage"

    if st.sidebar.button("📂 Export Statements"):
        st.session_state.nav = "export"

    if st.sidebar.button("📊 Analytics Dashboard"):
        st.session_state.nav = "analytics"

    if st.sidebar.button("📈 Product Trend (Last 6 Months)"):
        st.session_state.nav = "trend"

else: # user
    if st.sidebar.button("➕ Create Statement"):
        st.session_state.nav = "create"

    if st.sidebar.button("🕘 Recent Submissions"):
        st.session_state.nav = "recent"

    if st.sidebar.button("📁 My Reports"):
        st.session_state.nav = "reports"

if st.sidebar.button("🚪 Logout"):
    logout()


# ================= ADMIN SCREENS =================
if role == "admin":

    if st.session_state.nav == "home":
        st.header("Welcome Admin")
        st.write("Use the sidebar to navigate.")

    if st.session_state.nav == "manage":
        st.header("⚙️ Manage Database")
        st.write("Add/Edit/Delete Users, Products, Stockists, Allocations")
        st.info("This screen will reuse your CRUD code from previous version.")

        # TODO: your CRUD code here (unchanged)

    if st.session_state.nav == "export":
        st.header("📂 Export Statements")
        st.write("Filter and download statements.")
        st.info("This screen will reuse your Export PDF/CSV code.")

        # TODO: your export code here (unchanged)

    if st.session_state.nav == "analytics":
        st.header("📊 Analytics Dashboard")
        st.write("View territory insights with filters.")
        st.info("This screen will reuse your analytics code.")

        # TODO: analytics code here (unchanged)

    if st.session_state.nav == "trend":
        st.header("📈 Last 6-Month Product Trend")
        st.write("Select stockist and product to view trend.")
        st.info("This screen will reuse your trend code.")

        # TODO: trend code here (unchanged)
# ================= USER SCREENS =================
if role == "user":

    # HOME
    if st.session_state.nav == "home":
        st.header("Welcome User")
        st.write("Use sidebar to create a statement or view reports.")

    # =========================================
    # CREATE STATEMENT
    # =========================================
    if st.session_state.nav == "create":
        st.header("➕ Create Monthly Statement")

        # select stockist assigned to user
        uid = st.session_state.user["id"]

        allocs = supabase.table("user_stockists").select("*")\
            .eq("user_id", uid).execute().data

        stock_ids = [a["stockist_id"] for a in allocs]
        stockists = [
            s for s in supabase.table("stockists").select("*").execute().data
            if s["id"] in stock_ids
        ]

        if not stockists:
            st.error("No stockists assigned.")
            st.stop()

        st.session_state.selected_stockist = st.selectbox(
            "Select Stockist", [s["name"] for s in stockists]
        )

        # select year + month
        st.session_state.year = st.selectbox("Year", ["2024","2025","2026"])
        st.session_state.month = st.selectbox(
            "Month",
            ["January","February","March","April","May","June",
             "July","August","September","October","November","December"]
        )

        st.session_state.from_date = st.date_input("From date")
        st.session_state.to_date = st.date_input("To date")

        if st.button("Temporary Submit"):
            # insert statement if not exists
            stock_id = next(s["id"] for s in stockists 
                            if s["name"] == st.session_state.selected_stockist)

            res = supabase.table("sales_stock_statements").insert({
                "user_id": uid,
                "stockist_id": stock_id,
                "year": st.session_state.year,
                "month": st.session_state.month,
                "from_date": str(st.session_state.from_date),
                "to_date": str(st.session_state.to_date)
            }).execute()

            st.session_state.statement_id = res.data[0]["id"]

            # load products
            st.session_state.products_cache = supabase.table("products")\
                .select("*").execute().data

            st.session_state.product_index = 0
            st.session_state.nav = "product_entry"
            st.rerun()

    # =========================================
    # PRODUCT ENTRY SCREEN
    # =========================================
    if st.session_state.nav == "product_entry":
        st.header("Product Entry")

        products = st.session_state.products_cache
        idx = st.session_state.product_index

        product = products[idx]
        st.subheader(f"Product: {product['name']}")

        # last month info
        # fetch last statement for same stockist
        stockist_id = next(s["id"] for s in supabase.table("stockists")\
                           .select("*").execute().data
                           if s["name"] == st.session_state.selected_stockist)

        # last statement for that stockist BEFORE current from_date
        last_stmt = supabase.table("sales_stock_statements")\
            .select("*")\
            .eq("stockist_id", stockist_id)\
            .lt("from_date", str(st.session_state.from_date))\
            .order("from_date", desc=True).limit(1).execute().data

        last_closing = 0
        last_diff = 0
        last_issue = 0

        if last_stmt:
            last_items = supabase.table("sales_stock_items").select("*")\
                .eq("statement_id", last_stmt[0]["id"])\
                .eq("product_id", product["id"]).execute().data
            if last_items:
                last_closing = last_items[0]["closing"]
                last_diff = last_items[0]["diff_closing"]
                last_issue = last_items[0]["issue"]

        st.info(f"Last Month Closing: {last_closing}")
        st.info(f"Last Month Difference: {last_diff}")

        # user entry
        opening = st.number_input("Opening", value=last_closing, min_value=0)
        purchase = st.number_input("Purchase", value=0, min_value=0)
        issue = st.number_input("Issue", value=0, min_value=0)
        closing = st.number_input("Closing", value=0, min_value=0)

        # difference calculation (integer)
        diff = opening + purchase - issue - closing
        st.warning(f"Difference: {diff}")

        # store temporarily
        st.session_state.product_data[product["id"]] = {
            "opening": opening,
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "diff_closing": diff,
            "prev_issue": last_issue
        }

        # NAV BUTTONS
        cols = st.columns(3)

        # Previous product
        if cols[0].button("Previous Product") and idx > 0:
            st.session_state.product_index -= 1
            st.rerun()

        # Next / End
        if idx < len(products) - 1:
            if cols[1].button("Next Product"):
                st.session_state.product_index += 1
                st.rerun()
        else:
            if cols[1].button("End of Products"):
                st.session_state.nav = "preview"
                st.rerun()

    # =========================================
    # PREVIEW
    # =========================================
    if st.session_state.nav == "preview":
        st.header("Preview Statement")

        pid_list = st.session_state.products_cache

        for i, p in enumerate(pid_list):
            d = st.session_state.product_data.get(p["id"], None)

            if d:
                cols = st.columns(6)
                cols[0].write(p["name"])
                cols[1].write(d["opening"])
                cols[2].write(d["issue"])
                cols[3].write(d["closing"])
                cols[4].write(d["diff_closing"])

                # edit button
                if cols[5].button("Edit", key=f"edit_{i}"):
                    st.session_state.product_index = i
                    st.session_state.nav = "product_entry"
                    st.rerun()

        if st.button("Final Submit"):
            # insert items
            for pid, d in st.session_state.product_data.items():
                supabase.table("sales_stock_items").insert({
                    "statement_id": st.session_state.statement_id,
                    "product_id": pid,
                    "opening": d["opening"],
                    "purchase": d["purchase"],
                    "issue": d["issue"],
                    "closing": d["closing"],
                    "diff_closing": d["diff_closing"]
                }).execute()

            st.success("Statement Submitted!")
            st.session_state.nav = "recent"
            st.rerun()

    # =========================================
    # RECENT SUBMISSIONS
    # =========================================
    if st.session_state.nav == "recent":
        st.header("Recent Submissions")

        stmts = supabase.table("sales_stock_statements")\
            .select("*")\
            .eq("user_id", st.session_state.user["id"]).execute().data

        for s in stmts:
            stock = supabase.table("stockists").select("name")\
                .eq("id", s["stockist_id"]).execute().data[0]["name"]
            st.write(f"{s['month']} {s['year']} — {stock}")

            if st.button("View Report", key=f"view_{s['id']}"):
                st.session_state.nav = "reports"
                st.session_state.statement_id = s["id"]
                st.rerun()

    # =========================================
    # REPORTS PAGE
    # =========================================
    if st.session_state.nav == "reports":
        st.header("📁 Statement Report")

        sid = st.session_state.statement_id
        if not sid:
            st.write("No report selected.")
            st.stop()

        stmt = supabase.table("sales_stock_statements")\
            .select("*").eq("id", sid).execute().data[0]

        stock = supabase.table("stockists")\
            .select("name").eq("id", stmt["stockist_id"]).execute().data[0]["name"]

        items = supabase.table("sales_stock_items")\
            .select("*").eq("statement_id", sid).execute().data

        st.subheader(f"{stmt['month']} {stmt['year']} — {stock}")

        for it in items:
            pname = supabase.table("products").select("name")\
                .eq("id", it["product_id"]).execute().data[0]["name"]

            st.write(
                f"{pname} | O:{it['opening']} P:{it['purchase']} "
                f"I:{it['issue']} C:{it['closing']} D:{it['diff_closing']}"
            )

        # PDF download
        if st.button("Download PDF"):
            text = "\n".join([
                f"Stockist: {stock}",
                f"Month: {stmt['month']} {stmt['year']}",
                "-"*30
            ])
            for it in items:
                pname = supabase.table("products").select("name")\
                    .eq("id", it["product_id"]).execute().data[0]["name"]
                text += f"\n{pname}: {it['opening']} {it['purchase']} {it['issue']} {it['closing']} {it['diff_closing']}"

            pdf = generate_pdf(text)
            st.download_button("Download", pdf, "statement.pdf")
# ================= FOOTER =================
st.markdown("---")
st.markdown("© Ivy Pharmaceuticals")
