import streamlit as st
from supabase import create_client

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Sales & Stock App", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

# ---------------- LOGIN FUNCTION ----------------
def login(username, password):
    res = supabase.table("users") \
        .select("*") \
        .eq("username", username) \
        .eq("password", password) \
        .execute()

    if res.data:
        user = res.data[0]
        st.session_state.logged_in = True
        st.session_state.role = user["role"]
        st.session_state.username = user["username"]
        st.success("Login successful")
    else:
        st.error("Invalid username or password")

# ---------------- LOGOUT ----------------
def logout():
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None
    st.experimental_rerun()

# ---------------- UI ----------------
st.title("Sales & Stock Statement App")

if not st.session_state.logged_in:
    st.subheader("Login")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login as Admin"):
            st.session_state.login_mode = "admin"

    with col2:
        if st.button("Login as User"):
            st.session_state.login_mode = "user"

    if "login_mode" in st.session_state:
        st.write(f"Logging in as **{st.session_state.login_mode}**")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            login(username, password)

else:
    st.success(f"Logged in as {st.session_state.username} ({st.session_state.role})")

    if st.button("Logout"):
        logout()

    if st.session_state.role == "admin":
        st.header("Admin Dashboard (Coming next)")
    else:
        st.header("User Dashboard (Coming next)")
