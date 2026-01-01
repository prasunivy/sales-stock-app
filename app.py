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
# SESSION STATE
# ======================================================
for k in ["auth_user", "role"]:
    if k not in st.session_state:
        st.session_state[k] = None

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

    if not res.data[0].get("is_active", True):
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
    res = supabase.table("users").select("*").eq("id", user_id).execute()
    return res.data[0]
# ======================================================
# STATEMENT RESOLVER (ENGINE CORE)
# ======================================================

def resolve_statement(user_id, stockist_id, year, month):
    res = supabase.table("statements") \
        .select("*") \
        .eq("stockist_id", stockist_id) \
        .eq("year", year) \
        .eq("month", month) \
        .execute()

    if not res.data:
        return {
            "mode": "create",
            "statement": None
        }

    stmt = res.data[0]

    if stmt["status"] == "final":
        return {
            "mode": "view",
            "statement": stmt
        }

    if stmt.get("locked"):
        return {
            "mode": "locked",
            "statement": stmt
        }

    return {
        "mode": "edit",
        "statement": stmt
    }

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
# USER LANDING PAGE
# ======================================================

if role == "user":

    st.title("📊 Sales & Stock Statement")

    st.markdown("### Choose an action")

    col1, col2, col3 = st.columns(3)

    with col1:
        create_clicked = st.button("➕ Create", use_container_width=True)

    with col2:
        edit_clicked = st.button("✏️ Edit", use_container_width=True)

    with col3:
        view_clicked = st.button("👁 View", use_container_width=True)
    st.divider()
    st.subheader("Statement Period")

    stockists = supabase.table("user_stockists") \
        .select("stockist_id, stockists(name)") \
        .eq("user_id", user_id) \
        .execute().data

    if not stockists:
        st.warning("No stockists allocated to you")
        st.stop()

    selected_stockist = st.selectbox(
        "Stockist",
        stockists,
        format_func=lambda x: x["stockists"]["name"]
    )

    current_year = datetime.now().year
    current_month = datetime.now().month

    year = st.selectbox(
        "Year",
        [current_year - 1, current_year]
    )

    month = st.selectbox(
        "Month",
        list(range(1, current_month + 1))
    )
    action = None
    if create_clicked:
        action = "create"
    elif edit_clicked:
        action = "edit"
    elif view_clicked:
        action = "view"

    if action:
        result = resolve_statement(
            user_id=user_id,
            stockist_id=selected_stockist["stockist_id"],
            year=year,
            month=month
        )

        if action == "create":
            if result["mode"] == "create":
                st.success("No statement exists. You can create a new one.")
            elif result["mode"] == "edit":
                st.info("Draft statement exists. Redirecting to edit.")
            elif result["mode"] == "locked":
                st.error("Statement already locked.")
                st.stop()
            elif result["mode"] == "view":
                st.warning("Statement already finalized. Use View.")
                st.stop()

        if action == "edit":
            if result["mode"] == "edit":
                st.success("Opening draft statement for edit.")
            elif result["mode"] == "create":
                st.error("No draft exists. Please create first.")
                st.stop()
            elif result["mode"] == "locked":
                st.error("Statement already locked.")
                st.stop()
            elif result["mode"] == "view":
                st.error("Statement already finalized. Edit not allowed.")
                st.stop()

        if action == "view":
            if result["statement"]:
                st.success("Opening statement in view mode.")
            else:
                st.error("No statement exists for this period.")
                st.stop()

# ======================================================
# ADMIN PANEL
# ======================================================
if role == "admin":
    st.title("Admin Dashboard")

    section = st.radio(
        "Admin Section",
        [
            "Statements",
            "Users",
            "Create User",
            "Stockists",
            "Products",
            "Reset User Password",
            "Audit Logs",
            "Lock / Unlock Statements"
        ]
    )

    # -------- STATEMENTS ----------
    if section == "Statements":
        st.dataframe(pd.DataFrame(
            supabase.table("statements").select("*").execute().data
        ))

    # -------- USERS (FULL RESTORED) ----------
    elif section == "Users":
        st.subheader("👤 Edit User & Reassign Stockists")

        users = supabase.table("users") \
            .select("id, username, role, is_active") \
            .order("username") \
            .execute().data

        user = st.selectbox("Select User", users, format_func=lambda x: x["username"])

        is_active = st.checkbox("User Active", value=user["is_active"])

        all_stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data

        assigned = supabase.table("user_stockists") \
            .select("stockist_id") \
            .eq("user_id", user["id"]) \
            .execute().data

        assigned_ids = [a["stockist_id"] for a in assigned]

        selected_stockists = st.multiselect(
            "Assigned Stockists",
            all_stockists,
            default=[s for s in all_stockists if s["id"] in assigned_ids],
            format_func=lambda x: x["name"]
        )

        if st.button("Save Changes"):
            supabase.table("users").update({
                "is_active": is_active,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", user["id"]).execute()

            supabase.table("user_stockists").delete() \
                .eq("user_id", user["id"]).execute()

            for s in selected_stockists:
                supabase.table("user_stockists").insert({
                    "user_id": user["id"],
                    "stockist_id": s["id"]
                }).execute()

            supabase.table("audit_logs").insert({
                "action": "update_user",
                "target_type": "user",
                "target_id": user["id"],
                "performed_by": user_id,
                "metadata": {
                    "is_active": is_active,
                    "stockists": [s["name"] for s in selected_stockists]
                }
            }).execute()

            st.success("User updated")

    # -------- CREATE USER ----------
    elif section == "Create User":
        st.subheader("➕ Create User")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Create User"):
            email = f"{username}@internal.local"

            auth_user = admin_supabase.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True
            })

            supabase.table("users").insert({
                "id": auth_user.user.id,
                "username": username,
                "role": "user",
                "is_active": True
            }).execute()

            st.success("User created")

    # -------- STOCKISTS (FULL RESTORED) ----------
    elif section == "Stockists":
        st.subheader("🏪 Stockists Management")

        st.markdown("### ➕ Add Stockist")
        name = st.text_input("Stockist Name")

        if st.button("Add Stockist"):
            supabase.table("stockists").insert({
                "name": name,
                "created_by": user_id
            }).execute()

            supabase.table("audit_logs").insert({
                "action": "create_stockist",
                "target_type": "stockist",
                "performed_by": user_id,
                "metadata": {"name": name}
            }).execute()

            st.success("Stockist added")
            st.rerun()

        st.divider()

        stockists = supabase.table("stockists") \
            .select("*") \
            .order("name") \
            .execute().data

        if stockists:
            stockist = st.selectbox(
                "Select Stockist",
                stockists,
                format_func=lambda x: x["name"]
            )

            edit_name = st.text_input("Name", value=stockist["name"])

            if st.button("Save Changes"):
                supabase.table("stockists").update({
                    "name": edit_name
                }).eq("id", stockist["id"]).execute()

                supabase.table("audit_logs").insert({
                    "action": "update_stockist",
                    "target_type": "stockist",
                    "target_id": stockist["id"],
                    "performed_by": user_id,
                    "metadata": {"name": edit_name}
                }).execute()

                st.success("Updated")
                st.rerun()

            if st.button("Delete Stockist"):
                used = supabase.table("statements") \
                    .select("id") \
                    .eq("stockist_id", stockist["id"]) \
                    .limit(1) \
                    .execute().data

                if used:
                    st.error("Cannot delete stockist in use")
                else:
                    supabase.table("stockists") \
                        .delete() \
                        .eq("id", stockist["id"]) \
                        .execute()

                    st.success("Deleted")
                    st.rerun()

    # -------- PRODUCTS (FULL RESTORED) ----------
    elif section == "Products":
        st.subheader("📦 Product Master")

        # -------------------------------
        # ADD PRODUCT
        # -------------------------------
        name = st.text_input("Product Name")

        peak = st.multiselect("Peak Months", list(range(1, 13)))
        high = st.multiselect("High Months", list(range(1, 13)))
        low = st.multiselect("Low Months", list(range(1, 13)))
        lowest = st.multiselect("Lowest Months", list(range(1, 13)))

        if st.button("Add Product"):
            clean_name = name.strip()

            if not clean_name:
                st.error("Product name is required")
            else:
                existing = supabase.table("products") \
                    .select("id") \
                    .ilike("name", clean_name) \
                    .execute().data

                if existing:
                    st.error("Product already exists")
                else:
                    supabase.table("products").insert({
                        "name": clean_name,
                        "peak_months": peak,
                        "high_months": high,
                        "low_months": low,
                        "lowest_months": lowest
                    }).execute()

                    supabase.table("audit_logs").insert({
                        "action": "create_product",
                        "target_type": "product",
                        "performed_by": user_id,
                        "metadata": {
                            "name": clean_name,
                            "peak": peak,
                            "high": high,
                            "low": low,
                            "lowest": lowest
                        }
                    }).execute()

                    st.success("Product added successfully")
                    st.rerun()

        st.divider()

        # -------------------------------
        # EDIT / DELETE PRODUCT
        # -------------------------------
        products = supabase.table("products") \
            .select("*") \
            .order("name") \
            .execute().data

        if not products:
            st.info("No products found")
        else:
            product = st.selectbox(
                "Select Product",
                products,
                format_func=lambda x: x["name"]
            )

            edit_name = st.text_input(
                "Edit Product Name",
                value=product["name"]
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Save Changes"):
                    supabase.table("products").update({
                        "name": edit_name.strip()
                    }).eq("id", product["id"]).execute()

                    supabase.table("audit_logs").insert({
                        "action": "update_product",
                        "target_type": "product",
                        "target_id": product["id"],
                        "performed_by": user_id,
                        "metadata": {"name": edit_name}
                    }).execute()

                    st.success("Product updated")
                    st.rerun()

            with col2:
                if st.button("Delete Product"):
                    used = supabase.table("statement_products") \
                        .select("id") \
                        .eq("product_id", product["id"]) \
                        .limit(1) \
                        .execute().data

                    if used:
                        st.error("Cannot delete product used in statements")
                    else:
                        supabase.table("products") \
                            .delete() \
                            .eq("id", product["id"]) \
                            .execute()

                        supabase.table("audit_logs").insert({
                            "action": "delete_product",
                            "target_type": "product",
                            "target_id": product["id"],
                            "performed_by": user_id,
                            "metadata": {"name": product["name"]}
                        }).execute()

                        st.success("Product deleted")
                        st.rerun()

    # -------- RESET PASSWORD ----------
    elif section == "Reset User Password":
        users = supabase.table("users").select("id, username").execute().data
        u = st.selectbox("User", users, format_func=lambda x: x["username"])
        pwd = st.text_input("New Password", type="password")

        if st.button("Reset"):
            admin_supabase.auth.admin.update_user_by_id(u["id"], {"password": pwd})
            st.success("Password reset")

    # -------- AUDIT LOGS ----------
    elif section == "Audit Logs":
        logs = supabase.table("audit_logs") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute().data

        st.dataframe(pd.DataFrame(logs))

    # -------- LOCK / UNLOCK ----------
    elif section == "Lock / Unlock Statements":
        stmts = supabase.table("statements").select("*").execute().data
        s = st.selectbox("Statement", stmts, format_func=lambda x: f"{x['year']}-{x['month']}")

        if st.button("Lock"):
            supabase.table("statements").update({
                "status": "locked",
                "locked_at": datetime.utcnow(),
                "locked_by": user_id
            }).eq("id", s["id"]).execute()

            supabase.table("audit_logs").insert({
                "action": "lock_statement",
                "target_type": "statement",
                "target_id": s["id"],
                "performed_by": user_id
            }).execute()

            st.success("Locked")

        if st.button("Unlock"):
            supabase.table("statements").update({
                "status": "draft"
            }).eq("id", s["id"]).execute()

            supabase.table("audit_logs").insert({
                "action": "unlock_statement",
                "target_type": "statement",
                "target_id": s["id"],
                "performed_by": user_id
            }).execute()

            st.success("Unlocked")
