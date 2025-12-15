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
else:
    st.success(f"Logged in as {st.session_state.username} ({st.session_state.role})")

    if st.button("Logout"):
        logout()

    if st.session_state.role == "admin":
        st.header("Admin Dashboard")

        tab1, tab2, tab3 = st.tabs(["👤 Users", "📦 Products", "🏪 Stockists"])

        # ---------------- USERS ----------------
        with tab1:
            st.subheader("Add New User")

            new_username = st.text_input("Username", key="new_user")
            new_password = st.text_input("Password", type="password", key="new_pass")

            if st.button("Add User"):
                if new_username and new_password:
                    supabase.table("users").insert({
                        "username": new_username,
                        "password": new_password,
                        "role": "user"
                    }).execute()
                    st.success("User added")
                    st.experimental_rerun()
                else:
                    st.error("Enter username and password")

            st.divider()
            st.subheader("Existing Users")

            users = supabase.table("users").select("*").execute().data

            for u in users:
                if u["role"] == "user":
                    col1, col2 = st.columns([3, 1])
                    col1.write(u["username"])
                    if col2.button("Delete", key=f"del_user_{u['id']}"):
                        supabase.table("users").delete().eq("id", u["id"]).execute()
                        st.warning("User deleted")
                        st.experimental_rerun()

        # ---------------- PRODUCTS ----------------
        with tab2:
            st.subheader("Add Product")

            product_name = st.text_input("Product name")

            if st.button("Add Product"):
                if product_name:
                    supabase.table("products").insert({
                        "name": product_name
                    }).execute()
                    st.success("Product added")
                    st.experimental_rerun()

            st.divider()
            st.subheader("Product List")

            products = supabase.table("products").select("*").order("name").execute().data

            for p in products:
                col1, col2 = st.columns([3, 1])
                col1.write(p["name"])
                if col2.button("Delete", key=f"del_prod_{p['id']}"):
                    supabase.table("products").delete().eq("id", p["id"]).execute()
                    st.warning("Product deleted")
                    st.experimental_rerun()

        # ---------------- STOCKISTS ----------------
        with tab3:
            st.subheader("Add Stockist")

            stockist_name = st.text_input("Stockist name")

            if st.button("Add Stockist"):
                if stockist_name:
                    supabase.table("stockists").insert({
                        "name": stockist_name
                    }).execute()
                    st.success("Stockist added")
                    st.experimental_rerun()

            st.divider()
            st.subheader("Stockist List")

            stockists = supabase.table("stockists").select("*").order("name").execute().data

            for s in stockists:
                col1, col2 = st.columns([3, 1])
                col1.write(s["name"])
                if col2.button("Delete", key=f"del_stock_{s['id']}"):
                    supabase.table("stockists").delete().eq("id", s["id"]).execute()
                    st.warning("Stockist deleted")
                    st.experimental_rerun()

    else:
        st.header("User Dashboard (Coming next)")
