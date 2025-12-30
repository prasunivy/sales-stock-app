import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide",
    initial_sidebar_state="expanded"
)

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)
admin_supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
)
# ======================================================
# SESSION STATE INIT
# ======================================================
for key in ["auth_user", "role", "statement_id"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ======================================================
# UTILITIES
# ======================================================
def safe(fn, msg="Operation failed"):
    try:
        return fn()
    except Exception as e:
        st.error(f"{msg}: {e}")
        return None

def notify(msg):
    st.success(msg)

# ======================================================
# USERNAME → EMAIL (INTERNAL ONLY)
# ======================================================
def username_to_email(username):
    res = supabase.table("users").select("id").eq("username", username).execute()
    if not res.data:
        return None
    return f"{username}@internal.local"

# ======================================================
# AUTH
# ======================================================
def login(username, password):
    email = username_to_email(username)
    if not email:
        raise Exception("Invalid username")

    return supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

def load_profile(user_id):
    res = supabase.table("users").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None

# ======================================================
# STATEMENT FUNCTIONS
# ======================================================
def get_or_create_statement(user_id, stockist_id, year, month):
    res = supabase.table("statements") \
        .select("*") \
        .eq("stockist_id", stockist_id) \
        .eq("year", year) \
        .eq("month", month) \
        .execute()

    if res.data:
        return res.data[0]

    return supabase.table("statements").insert({
        "user_id": user_id,
        "stockist_id": stockist_id,
        "year": year,
        "month": month
    }).execute().data[0]

def lock_statement(statement_id):
    supabase.rpc("lock_statement", {"stmt": statement_id}).execute()

def save_product(statement_id, product_id, vals):
    supabase.table("statement_products").upsert({
        "statement_id": statement_id,
        "product_id": product_id,
        **vals,
        "updated_at": datetime.utcnow().isoformat()
    }).execute()

def final_submit(statement_id):
    supabase.table("statements").update({
        "status": "final",
        "final_submitted_at": datetime.utcnow().isoformat()
    }).eq("id", statement_id).execute()

# ======================================================
# LOGIN SCREEN
# ======================================================
if not st.session_state.auth_user:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            auth = login(username, password)
            profile = load_profile(auth.user.id)

            if not profile:
                st.error("User profile missing")
            else:
                st.session_state.auth_user = auth.user
                st.session_state.role = profile["role"]
                st.rerun()

        except Exception:
            st.error("Invalid username or password")

    st.stop()

# ======================================================
# SIDEBAR
# ======================================================
st.sidebar.title("Navigation")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

role = st.session_state.role
user_id = st.session_state.auth_user.id

# ======================================================
# USER PANEL
# ======================================================
if role == "user":
    st.title("User Dashboard")

    tab = st.radio("Action", ["Create / Resume", "View"])

    # -------- CREATE / RESUME ----------
    if tab == "Create / Resume":
        stockist_ids = supabase.table("user_stockists") \
            .select("stockist_id") \
            .eq("user_id", user_id) \
            .execute().data

        stockists = supabase.table("stockists") \
            .select("id,name") \
            .in_("id", [s["stockist_id"] for s in stockist_ids]) \
            .execute().data

        if not stockists:
            st.warning("No stockists allotted")
            st.stop()

        stockist = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])
        year = st.selectbox("Year", [datetime.now().year - 1, datetime.now().year])
        month = st.selectbox("Month", list(range(1, 13)))

        if st.button("Open Statement"):
            stmt = safe(lambda: get_or_create_statement(user_id, stockist["id"], year, month))
            if stmt:
                safe(lambda: lock_statement(stmt["id"]), "Statement open on another device")
                st.session_state.statement_id = stmt["id"]
                notify("Statement opened")
                st.rerun()

    # -------- PRODUCT ENTRY ----------
    if st.session_state.statement_id:
        st.subheader("Product Entry")

        products = supabase.table("products").select("*").order("name").execute().data

        for p in products:
            st.markdown(f"### {p['name']}")

            c1, c2, c3, c4 = st.columns(4)
            opening = c1.number_input("Opening", 0.0, key=f"o_{p['id']}")
            purchase = c2.number_input("Purchase", 0.0, key=f"p_{p['id']}")
            issue = c3.number_input("Issue", 0.0, key=f"i_{p['id']}")
            closing = c4.number_input("Closing", 0.0, key=f"c_{p['id']}")

            diff = opening + purchase - issue - closing
            st.caption(f"Difference: {diff}")

            if st.button("Save", key=f"s_{p['id']}"):
                save_product(
                    st.session_state.statement_id,
                    p["id"],
                    dict(opening=opening, purchase=purchase, issue=issue, closing=closing)
                )
                notify("Saved")

        if st.button("Final Submission"):
            final_submit(st.session_state.statement_id)
            notify("Statement submitted")
            st.session_state.statement_id = None
            st.rerun()

    # -------- VIEW ----------
    if tab == "View":
        data = supabase.table("statements") \
            .select("year,month,status") \
            .eq("user_id", user_id) \
            .execute().data

        st.dataframe(pd.DataFrame(data))

# ======================================================
# ADMIN PANEL
# ======================================================
if role == "admin":
    st.subheader("🔐 Reset User Password")

    users = supabase.table("users").select("id, username").execute().data
    user = st.selectbox("Select User", users, format_func=lambda x: x["username"])

    new_password = st.text_input("New Password", type="password")

    if st.button("Reset Password"):
        if len(new_password) < 6:
            st.error("Password must be at least 6 characters")
        else:
            # Reset password via Supabase Auth (ADMIN API)
            admin_supabase.auth.admin.update_user_by_id(
                user["id"],
                {"password": new_password}
            )

            # Audit trail
            supabase.table("users").update({
                "last_password_reset_at": datetime.utcnow().isoformat(),
                "password_reset_by": st.session_state.auth_user.id
            }).eq("id", user["id"]).execute()

            st.success(f"Password reset for user: {user['username']}")
if role == "admin":
    st.title("Admin Dashboard")

    section = st.radio("Admin Section", ["Statements", "Users", "Stockists"])

    if section == "Statements":
        st.dataframe(pd.DataFrame(
            supabase.table("statements").select("*").execute().data
        ))

    if section == "Users":
        st.dataframe(pd.DataFrame(
            supabase.table("users").select("*").execute().data
        ))

    if section == "Stockists":
        st.dataframe(pd.DataFrame(
            supabase.table("stockists").select("*").execute().data
        ))
