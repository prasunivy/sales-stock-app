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
for k in ["auth_user", "role", "statement_id"]:
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
        "Products",  # 👈 ADD THIS
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

    # -------- USERS (EDIT & REASSIGN STOCKISTS) ----------
    elif section == "Users":
        st.subheader("👤 Edit User & Reassign Stockists")

        users = supabase.table("users") \
            .select("id, username, role, is_active") \
            .order("username") \
            .execute().data

        selected_user = st.selectbox(
            "Select User",
            users,
            format_func=lambda x: x["username"]
        )

        new_username = st.text_input(
            "Username",
            value=selected_user["username"]
        )

        is_active = st.checkbox(
            "User Active",
            value=selected_user.get("is_active", True)
        )

        all_stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data

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
            supabase.table("users").update({
                "username": new_username,
                "is_active": is_active,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", selected_user["id"]).execute()

            supabase.table("user_stockists").delete() \
                .eq("user_id", selected_user["id"]).execute()

            for s in selected_stockists:
                supabase.table("user_stockists").insert({
                    "user_id": selected_user["id"],
                    "stockist_id": s["id"]
                }).execute()

            supabase.table("audit_logs").insert({
                "action": "update_user",
                "target_type": "user",
                "target_id": selected_user["id"],
                "performed_by": user_id,
                "metadata": {
                    "username": new_username,
                    "is_active": is_active,
                    "stockists": [s["name"] for s in selected_stockists]
                }
            }).execute()

            st.success("User updated successfully")

    # -------- CREATE USER ----------
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
            email = f"{new_username}@internal.local"

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

            st.success(f"User '{new_username}' created")

    # -------- STOCKISTS (CREATE / EDIT / DELETE) ----------
    
    elif section == "Stockists":
        st.subheader("🏪 Stockists Management")

        # ===============================
        # CREATE STOCKIST
        # ===============================
        st.markdown("### ➕ Add New Stockist")

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Stockist Name", key="new_stockist_name")
            location = st.text_input("Location", key="new_stockist_location")
        with col2:
            phone = st.text_input("Phone", key="new_stockist_phone")
            payment_terms = st.number_input(
                "Payment Terms (days)",
                min_value=0,
                step=1,
                key="new_stockist_terms"
            )

        if st.button("Add Stockist", key="add_stockist_btn"):
            if not name.strip():
                st.error("Stockist name is required")
            else:
                existing = supabase.table("stockists") \
                    .select("id") \
                    .ilike("name", name.strip()) \
                    .execute().data

                if existing:
                    st.warning("Stockist already exists")
                else:
                    supabase.table("stockists").insert({
                        "name": name.strip(),
                        "location": location.strip(),
                        "phone": phone.strip(),
                        "payment_terms": payment_terms,
                        "created_by": user_id
                    }).execute()

                    supabase.table("audit_logs").insert({
                        "action": "create_stockist",
                        "target_type": "stockist",
                        "performed_by": user_id,
                        "metadata": {
                            "name": name,
                            "location": location,
                            "phone": phone,
                            "payment_terms": payment_terms
                        }
                    }).execute()

                    st.success("Stockist added successfully")
                    st.rerun()

        st.divider()

        # ===============================
        # EDIT / DELETE STOCKIST
        # ===============================
        st.markdown("### ✏️ Edit / Delete Stockist")

        stockists = supabase.table("stockists") \
            .select("id, name, location, phone, payment_terms") \
            .order("name") \
            .execute().data

        if not stockists:
            st.info("No stockists available")
            st.stop()

        stockist = st.selectbox(
            "Select Stockist",
            stockists,
            format_func=lambda x: x["name"],
            key="edit_stockist_select"
        )

        col1, col2 = st.columns(2)
        with col1:
            edit_name = st.text_input(
                "Name",
                value=stockist["name"],
                key=f"edit_name_{stockist['id']}"
            )
            edit_location = st.text_input(
                "Location",
                value=stockist["location"] or "",
                key=f"edit_location_{stockist['id']}"
            )
        with col2:
            edit_phone = st.text_input(
                "Phone",
                value=stockist["phone"] or "",
                key=f"edit_phone_{stockist['id']}"
            )
            edit_terms = st.number_input(
                "Payment Terms (days)",
                min_value=0,
                step=1,
                value=stockist["payment_terms"] or 0,
                key=f"edit_terms_{stockist['id']}"
            )

        col_save, col_delete = st.columns(2)

        # -------- UPDATE ----------
        with col_save:
            if st.button("💾 Save Changes", key=f"save_stockist_{stockist['id']}"):
                supabase.table("stockists").update({
                    "name": edit_name.strip(),
                    "location": edit_location.strip(),
                    "phone": edit_phone.strip(),
                    "payment_terms": edit_terms
                }).eq("id", stockist["id"]).execute()

                supabase.table("audit_logs").insert({
                    "action": "update_stockist",
                    "target_type": "stockist",
                    "target_id": stockist["id"],
                    "performed_by": user_id,
                    "metadata": {
                        "name": edit_name,
                        "location": edit_location,
                        "phone": edit_phone,
                        "payment_terms": edit_terms
                    }
                }).execute()

                st.success("Stockist updated successfully")
                st.rerun()

        # -------- DELETE ----------
        with col_delete:
            if st.button("🗑️ Delete Stockist", key=f"delete_stockist_{stockist['id']}"):
                used_stmt = supabase.table("statements") \
                    .select("id") \
                    .eq("stockist_id", stockist["id"]) \
                    .limit(1) \
                    .execute().data

                used_alloc = supabase.table("user_stockists") \
                    .select("id") \
                    .eq("stockist_id", stockist["id"]) \
                    .limit(1) \
                    .execute().data

                if used_stmt or used_alloc:
                    st.error(
                        "Cannot delete stockist. "
                        "It is used in statements or assigned to users."
                    )
                else:
                    supabase.table("stockists") \
                        .delete() \
                        .eq("id", stockist["id"]) \
                        .execute()

                    supabase.table("audit_logs").insert({
                        "action": "delete_stockist",
                        "target_type": "stockist",
                        "target_id": stockist["id"],
                        "performed_by": user_id,
                        "metadata": {"name": stockist["name"]}
                    }).execute()

                    st.success("Stockist deleted successfully")
                    st.rerun()

    elif section == "Products":
    st.subheader("📦 Product Master")

    # ===============================
    # ADD NEW PRODUCT
    # ===============================
    st.markdown("### ➕ Add New Product")

    col1, col2 = st.columns(2)

    with col1:
        product_name = st.text_input("Product Name")

    with col2:
        peak_months = st.multiselect("Peak Months", list(range(1, 13)))
        high_months = st.multiselect("High Months", list(range(1, 13)))
        low_months = st.multiselect("Low Months", list(range(1, 13)))
        lowest_months = st.multiselect("Lowest Months", list(range(1, 13)))

    if st.button("Add Product"):
        if not product_name.strip():
            st.error("Product name is required")
        else:
            existing = supabase.table("products") \
                .select("id") \
                .ilike("name", product_name.strip()) \
                .execute().data

            if existing:
                st.warning("Product already exists")
            else:
                supabase.table("products").insert({
                    "name": product_name.strip(),
                    "peak_months": peak_months,
                    "high_months": high_months,
                    "low_months": low_months,
                    "lowest_months": lowest_months
                }).execute()

                st.success("Product added successfully")
                st.rerun()

    st.divider()

    # ===============================
    # EDIT / DELETE PRODUCT
    # ===============================
    st.markdown("### ✏️ Edit / Delete Product")

    products = supabase.table("products") \
        .select("*") \
        .order("name") \
        .execute().data

    if not products:
        st.info("No products found")
        st.stop()

    product = st.selectbox(
        "Select Product",
        products,
        format_func=lambda x: x["name"]
    )

    col1, col2 = st.columns(2)

    with col1:
        edit_name = st.text_input(
            "Product Name",
            value=product["name"]
        )

    with col2:
        edit_peak = st.multiselect(
            "Peak Months",
            list(range(1, 13)),
            default=product.get("peak_months") or []
        )
        edit_high = st.multiselect(
            "High Months",
            list(range(1, 13)),
            default=product.get("high_months") or []
        )
        edit_low = st.multiselect(
            "Low Months",
            list(range(1, 13)),
            default=product.get("low_months") or []
        )
        edit_lowest = st.multiselect(
            "Lowest Months",
            list(range(1, 13)),
            default=product.get("lowest_months") or []
        )

    col_save, col_delete = st.columns(2)

    # -------- UPDATE ----------
    with col_save:
        if st.button("💾 Save Changes"):
            supabase.table("products").update({
                "name": edit_name.strip(),
                "peak_months": edit_peak,
                "high_months": edit_high,
                "low_months": edit_low,
                "lowest_months": edit_lowest
            }).eq("id", product["id"]).execute()

            st.success("Product updated successfully")
            st.rerun()

    # -------- DELETE ----------
    with col_delete:
        if st.button("🗑️ Delete Product"):
            used = supabase.table("statement_products") \
                .select("id") \
                .eq("product_id", product["id"]) \
                .limit(1) \
                .execute().data

            if used:
                st.error("Cannot delete product. It is already used in statements.")
            else:
                supabase.table("products") \
                    .delete() \
                    .eq("id", product["id"]) \
                    .execute()

                st.success("Product deleted successfully")
                st.rerun()

    # -------- RESET PASSWORD ----------
    elif section == "Reset User Password":
        st.subheader("🔐 Reset User Password")

        users = supabase.table("users").select("id, username").execute().data
        user = st.selectbox("Select User", users, format_func=lambda x: x["username"])
        new_password = st.text_input("New Password", type="password")

        if st.button("Reset Password"):
            admin_supabase.auth.admin.update_user_by_id(
                user["id"],
                {"password": new_password}
            )
            st.success("Password reset successful")

    # -------- AUDIT LOGS ----------
    elif section == "Audit Logs":
        st.subheader("🧾 Audit Logs")

        logs = supabase.table("audit_logs") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute().data

        st.dataframe(pd.DataFrame(logs), use_container_width=True)
    # -------- LOCK / UNLOCK STATEMENTS ----------
    elif section == "Lock / Unlock Statements":
        st.subheader("🔒 Lock / Unlock Statements")

        statements = supabase.table("statements") \
            .select("id, year, month, stockist_id, status") \
            .order("year", desc=True) \
            .order("month", desc=True) \
            .execute().data

        if not statements:
            st.info("No statements found")
            st.stop()

        stmt = st.selectbox(
            "Select Statement",
            statements,
            format_func=lambda x: f"{x['year']}-{x['month']} | Stockist {x['stockist_id']} | {x.get('status', 'draft')}"
        )

        current_status = stmt.get("status", "draft")
        st.info(f"Current Status: {current_status.upper()}")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔒 Lock Statement"):
                supabase.table("statements").update({
                    "status": "locked",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", stmt["id"]).execute()

                supabase.table("audit_logs").insert({
                    "action": "lock_statement",
                    "target_type": "statement",
                    "target_id": stmt["id"],
                    "performed_by": user_id,
                    "metadata": {
                        "previous_status": current_status
                    }
                }).execute()

                st.success("Statement locked successfully")
                st.rerun()

        with col2:
            if st.button("🔓 Unlock Statement"):
                supabase.table("statements").update({
                    "status": "draft",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", stmt["id"]).execute()

                supabase.table("audit_logs").insert({
                    "action": "unlock_statement",
                    "target_type": "statement",
                    "target_id": stmt["id"],
                    "performed_by": user_id,
                    "metadata": {
                        "previous_status": current_status
                    }
                }).execute()

                st.success("Statement unlocked successfully")
                st.rerun()
