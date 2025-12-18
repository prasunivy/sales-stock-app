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
def init_session():
    for k,v in {
        "logged_in": False,
        "user": None,
        "nav": "home",
        "statement_id": None,
        "selected_stockist_id": None,
        "current_statement_from_date": None,
        "product_index": 0,
        "product_data": {},
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

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
    init_session()
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
    st.subheader("Login to Continue")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        login(username, password)

    st.stop()

# ================= SIDEBAR NAV =================
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

else:  # user
    if st.sidebar.button("➕ Create Statement"):
        st.session_state.nav = "create"

    if st.sidebar.button("🕘 Recent Submissions"):
        st.session_state.nav = "recent"

    if st.sidebar.button("📁 My Reports"):
        st.session_state.nav = "reports"

if st.sidebar.button("🚪 Logout"):
    logout()


# ================= ADMIN NAVIGATION SCREENS =================
if role == "admin":

    if st.session_state.nav == "home":
        st.header("Welcome Admin")
        st.write("Use the sidebar to navigate between admin functions.")

    # -------- ADMIN CRUD --------
    if st.session_state.nav == "manage":
        st.header("⚙️ Manage Database")
        st.write("Add / Edit / Delete Users, Products, Stockists, Allocations")
        st.info("This contains the CRUD functionality (same as before).")

        # reuse your CRUD code here
        st.write(" ... (CRUD code remains unchanged) ...")

    # -------- EXPORT --------
    if st.session_state.nav == "export":
        st.header("📂 Export Statements")
        st.write("Filter and Download CSV or PDF Reports")
        st.info("Existing export filters apply here.")

        # reuse your export code here
        st.write(" ... (export code remains unchanged) ...")

    # -------- ANALYTICS --------
    if st.session_state.nav == "analytics":
        st.header("📊 Analytics Dashboard")
        st.write("Apply filters to visualize product, stockist, and user trends.")

        # reuse analytics code here
        st.write(" ... (analytics code remains unchanged) ...")

    # -------- PRODUCT TREND --------
    if st.session_state.nav == "trend":
        st.header("📈 Last 6-Month Product Movement Trend")
        st.write("Select stockist and product to view recent trends.")

        # reuse trend code here
        st.write(" ... (trend code remains unchanged) ...")


# ================= USER NAVIGATION SCREENS =================
else:
    if st.session_state.nav == "home":
        st.header("Welcome User")
        st.write("Use the sidebar to create or view statements.")

    if st.session_state.nav == "create":
        st.header("➕ Create New Statement")
        st.write(" ... (existing create statement UI) ...")

    if st.session_state.nav == "recent":
        st.header("🕘 Recent Submissions")
        st.write(" ... (existing recent submissions) ...")

    if st.session_state.nav == "reports":
        st.header("📁 My Reports")
        st.write(" ... (existing PDF viewer / WhatsApp logic) ...")


# ================= FOOTER =================
st.markdown("---")
st.markdown("© Ivy Pharmaceuticals")
