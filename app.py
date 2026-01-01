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

# Public client (RLS enforced)
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"]
)

# Admin client (service role – admin-only operations)
admin_supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
)

# ======================================================
# SESSION STATE
# ======================================================
for k in ["auth_user", "role", "statement_id"]:
    if k not in st.session_state:
        st.session_state[k] = None

# ======================================================
# HELPERS
# ======================================================
def safe(fn, msg="Operation failed"):
    try:
        return fn()
    except Exception as e:
        st.error(f"{msg}: {e}")
        return None

# ======================================================
# USERNAME → INTERNAL EMAIL
# ======================================================
def username_to_email(username: str):
    res = supabase.table("users") \
        .select("id, is_active") \
        .eq("username", username) \
        .execute()

    if not res.data:
        return None

    if not res.data[0]["is_active"]:
        raise Exception("Account disabled")

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
    res = supabase.table("users") \
        .select("*") \
        .eq("id", user_id) \
        .execute()
    return res.data[0] if res.data else None

# ======================================================
# STATEMENT LOGIC (unchanged core)
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

# ======================================================
# LOGIN UI
# ======================================================
if not st.session_state.auth_user:
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            auth = login(username, password)
            profile = load_profile(auth.user.id)

            st.session_state.auth_user = auth.user
            st.session_state.role = profile["role"]
            st.rerun()

        except Exception as e:
            st.error(str(e))

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

    st.info("User data entry screens remain unchanged (safe recovery build).")

# ======================================================
# ADMIN PANEL
# ======================================================
if role == "admin":
    st.title("Admin Dashboard")

    section = st.radio(
        "Admin Section",
        ["Statements", "Users", "Create User", "Stockists", "Reset User Password"]
    )

    # -------- STATEMENTS ----------
    if section == "Statements":
        st.dataframe(pd.DataFrame(
            supabase.table("statements").select("*").execute().data
        ))

        # -------- USERS (EDIT & REASSIGN STOCKISTS) ----------
    elif section == "Users":
        st.subheader("👤 Edit User & Reassign Stockists")

        users = supabase.table("users") \
            .select("id, username, role, is_active") \
            .order("username") \
            .execute().data

        if not users:
            st.info("No users found")
            st.stop()

        selected_user = st.selectbox(
            "Select User",
            users,
            format_func=lambda x: x["username"]
        )

        # Current values
        new_username = st.text_input(
            "Username",
            value=selected_user["username"]
        )

        is_active = st.checkbox(
            "User Active",
            value=selected_user["is_active"]
        )

        # Fetch all stockists
        all_stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data

        # Fetch assigned stockists
        assigned = supabase.table("user_stockists") \
            .select("stockist_id") \
            .eq("user_id", selected_user["id"]) \
            .execute().data

        assigned_ids = [a["stockist_id"] for a in assigned]

        selected_stockists = st.multiselect(
            "Assigned Stockists",
            all_stockists,
            default=[s for s in all_stockists if s["id"] in assigned_ids],
            format_func=lambda x: x["name"]
        )

        if st.button("Save Changes"):
            try:
                # 1️⃣ Update users table
                supabase.table("users").update({
                    "username": new_username,
                    "is_active": is_active,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", selected_user["id"]).execute()

                # 2️⃣ Reset stockist assignments
                supabase.table("user_stockists") \
                    .delete() \
                    .eq("user_id", selected_user["id"]) \
                    .execute()

                for s in selected_stockists:
                    supabase.table("user_stockists").insert({
                        "user_id": selected_user["id"],
                        "stockist_id": s["id"]
                    }).execute()

                # 3️⃣ Audit log
                supabase.table("audit_logs").insert({
                    "action": "update_user",
                    "target_type": "user",
                    "target_id": selected_user["id"],
                    "performed_by": st.session_state.auth_user.id,
                    "metadata": {
                        "new_username": new_username,
                        "is_active": is_active,
                        "stockists": [s["name"] for s in selected_stockists]
                    }
                }).execute()

                st.success("User updated successfully")

            except Exception as e:
                st.error(f"Failed to update user: {e}")

    # -------- CREATE USER + ASSIGN STOCKISTS ----------
    elif section == "Create User":
        st.subheader("➕ Create User")

        stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data

        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")

        selected_stockists = st.multiselect(
            "Assign Stockists",
            stockists,
            format_func=lambda x: x["name"]
        )

        if st.button("Create User"):
            if not new_username:
                st.error("Username required")
                st.stop()

            if len(new_password) < 6:
                st.error("Password too short")
                st.stop()

            if not selected_stockists:
                st.error("Select at least one stockist")
                st.stop()

            email = f"{new_username}@internal.local"

            try:
                auth_user = admin_supabase.auth.admin.create_user({
                    "email": email,
                    "password": new_password,
                    "email_confirm": True
                })

                new_user_id = auth_user.user.id

                supabase.table("users").insert({
                    "id": new_user_id,
                    "username": new_username,
                    "role": "user",
                    "is_active": True
                }).execute()

                for s in selected_stockists:
                    supabase.table("user_stockists").insert({
                        "user_id": new_user_id,
                        "stockist_id": s["id"]
                    }).execute()

                supabase.table("audit_logs").insert({
                    "action": "create_user",
                    "target_type": "user",
                    "target_id": new_user_id,
                    "performed_by": user_id,
                    "metadata": {
                        "username": new_username,
                        "stockists": [s["name"] for s in selected_stockists]
                    }
                }).execute()

                st.success(f"User '{new_username}' created successfully")

            except Exception as e:
                st.error(f"Failed to create user: {e}")

    # -------- STOCKISTS ----------
    elif section == "Stockists":
        st.dataframe(pd.DataFrame(
            supabase.table("stockists").select("*").execute().data
        ))

    # -------- RESET PASSWORD ----------
    elif section == "Reset User Password":
        st.subheader("🔐 Reset User Password")

        users = supabase.table("users") \
            .select("id, username") \
            .execute().data

        user = st.selectbox("Select User", users, format_func=lambda x: x["username"])
        new_password = st.text_input("New Password", type="password")

        if st.button("Reset Password"):
            if len(new_password) < 6:
                st.error("Password too short")
            else:
                admin_supabase.auth.admin.update_user_by_id(
                    user["id"],
                    {"password": new_password}
                )

                supabase.table("users").update({
                    "last_password_reset_at": datetime.utcnow().isoformat(),
                    "password_reset_by": user_id
                }).eq("id", user["id"]).execute()

                st.success(f"Password reset for {user['username']}")
