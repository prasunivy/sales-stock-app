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
for k in [
    "auth_user", "role",
    "statement_id", "product_index",
    "statement_year", "statement_month",
    "engine_stage"
]:
    if k not in st.session_state:
        st.session_state[k] = None

# ======================================================
# SAFE EXEC
# ======================================================
def safe_exec(q, msg="Database error"):
    try:
        res = q.execute()
    except Exception as e:
        st.error(msg)
        st.exception(e)
        st.stop()

    if hasattr(res, "error") and res.error:
        st.error(msg)
        st.stop()

    return res.data or []

# ======================================================
# AUTH HELPERS
# ======================================================
def username_to_email(username):
    rows = safe_exec(
        supabase.table("users")
        .select("id,is_active")
        .eq("username", username),
        "Invalid username"
    )
    if not rows:
        return None
    if not rows[0]["is_active"]:
        raise Exception("Account disabled")
    return f"{username}@internal.local"

def login(username, password):
    email = username_to_email(username)
    if not email:
        raise Exception("Invalid username")
    return supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

def load_profile(uid):
    return safe_exec(
        supabase.table("users")
        .select("*")
        .eq("id", uid)
    )[0]

# ======================================================
# STATEMENT RESOLVER
# ======================================================
def resolve_statement(user_id, stockist_id, year, month):
    rows = safe_exec(
        supabase.table("statements")
        .select("*")
        .eq("user_id", user_id)
        .eq("stockist_id", stockist_id)
        .eq("year", year)
        .eq("month", month)
    )

    if not rows:
        return {"mode": "create", "statement": None}

    stmt = rows[0]
    if stmt["status"] == "final":
        return {"mode": "view", "statement": stmt}
    if stmt["status"] == "locked":
        return {"mode": "locked", "statement": stmt}
    return {"mode": "edit", "statement": stmt}

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
# USER LANDING
# ======================================================
if role == "user" and not st.session_state.statement_id:
    st.title("📊 Sales & Stock Statement")

    c1, c2, c3 = st.columns(3)
    create_clicked = c1.button("➕ Create", use_container_width=True)
    edit_clicked = c2.button("✏️ Edit", use_container_width=True)
    view_clicked = c3.button("👁 View", use_container_width=True)

    stockists = safe_exec(
        supabase.table("user_stockists")
        .select("stockist_id, stockists(name)")
        .eq("user_id", user_id)
    )

    if not stockists:
        st.warning("No stockists allocated")
        st.stop()

    selected_stockist = st.selectbox(
        "Stockist",
        stockists,
        format_func=lambda x: x["stockists"]["name"]
    )

    cy, cm = datetime.now().year, datetime.now().month
    year = st.selectbox("Year", [cy - 1, cy])
    month = st.selectbox(
        "Month",
        list(range(1, cm + 1)) if year == cy else list(range(1, 13))
    )

    action = "create" if create_clicked else "edit" if edit_clicked else "view" if view_clicked else None

    if action:
        result = resolve_statement(
            user_id,
            selected_stockist["stockist_id"],
            year,
            month
        )

        if action == "create":

            if result["mode"] == "create":
                res = admin_supabase.table("statements").insert(
                    {
                        "user_id": user_id,
                        "stockist_id": selected_stockist["stockist_id"],
                        "year": year,
                        "month": month,
                        "status": "draft",
                        "current_product_index": 0
                    },
                    returning="representation"
                ).execute()

                if not res.data:
                    st.error("Failed to create statement")
                    st.stop()

                stmt = res.data[0]

            elif result["mode"] == "edit":
                stmt = result["statement"]

            elif result["mode"] == "locked":
                st.error("Statement already locked")
                st.stop()

            else:
                st.warning("Statement already finalized")
                st.stop()

            if stmt.get("editing_by") and stmt["editing_by"] != user_id:
                st.error("Statement currently open on another device")
                st.stop()

            safe_exec(
                admin_supabase.table("statements")
                .update({
                    "editing_by": user_id,
                    "editing_at": datetime.utcnow().isoformat()
                })
                .eq("id", stmt["id"])
            )

            st.session_state.statement_id = stmt["id"]
            st.session_state.product_index = stmt["current_product_index"]
            st.session_state.statement_year = year
            st.session_state.statement_month = month
            st.session_state.engine_stage = stmt.get("engine_stage", "edit")
            st.rerun()

# ======================================================
# PRODUCT ENGINE
# ======================================================
if role == "user" and st.session_state.statement_id and st.session_state.engine_stage == "edit":
    sid = st.session_state.statement_id
    idx = st.session_state.product_index

    products = safe_exec(
        supabase.table("products").select("*").order("sort_order")
    )

    if idx >= len(products):
        safe_exec(
            admin_supabase.table("statements")
            .update({"engine_stage": "preview"})
            .eq("id", sid)
        )
        st.session_state.engine_stage = "preview"
        st.rerun()

    product = products[idx]
    st.subheader(
    f"Product {idx + 1} of {len(products)} — {product['name']}"
    )

    row = safe_exec(
        supabase.table("statement_products")
        .select("*")
        .eq("statement_id", sid)
        .eq("product_id", product["id"])
    )
    row = row[0] if row else {}

    opening = st.number_input("Opening", min_value=0.0, value=float(row.get("opening", 0)))
    purchase = st.number_input("Purchase", min_value=0.0, value=float(row.get("purchase", 0)))
    issue = st.number_input("Issue", min_value=0.0, value=float(row.get("issue", 0)))
    closing = st.number_input("Closing", min_value=0.0, value=float(row.get("closing", opening)))

    if st.button("💾 Save & Next"):
        safe_exec(
            admin_supabase.table("statement_products").upsert({
                "statement_id": sid,
                "product_id": product["id"],
                "opening": opening,
                "purchase": purchase,
                "issue": issue,
                "closing": closing,
                "updated_at": datetime.utcnow().isoformat()
            })
        )

        st.session_state.product_index += 1
        safe_exec(
            admin_supabase.table("statements")
            .update({"current_product_index": st.session_state.product_index})
            .eq("id", sid)
        )
        st.rerun()

# ======================================================
# PREVIEW & FINAL SUBMIT
# ======================================================
if role == "user" and st.session_state.engine_stage == "preview":
    sid = st.session_state.statement_id

    rows = safe_exec(
        supabase.table("statement_products")
        .select("opening,purchase,issue,closing,product_id,products(name)")
        .eq("statement_id", sid)
    )

    products = safe_exec(
        supabase.table("products").select("id")
    )

    if len(rows) != len(products):
        st.error("Incomplete products. Please finish all entries.")
        st.stop()

    df = pd.DataFrame([{
        "Product": r["products"]["name"] if r.get("products") else "UNKNOWN",
        "Opening": r["opening"],
        "Purchase": r["purchase"],
        "Issue": r["issue"],
        "Closing": r["closing"]
    } for r in rows])

    st.subheader("📋 Statement Preview")
    st.dataframe(df, use_container_width=True)

    if st.button("✅ Final Submit"):
        safe_exec(
            admin_supabase.table("statements")
            .update({
                "status": "final",
                "final_submitted_at": datetime.utcnow().isoformat(),
                "editing_by": None,
                "editing_at": None
            })
            .eq("id", sid)
        )

        st.session_state.clear()
        st.success("Statement finalized successfully")
        st.rerun()


# ======================================================
# ADMIN PANEL — FULL CRUD RESTORED
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
            "Lock / Unlock Statements",
            "Analytics"
        ]
    )

    # --------------------------------------------------
    # STATEMENTS
    # --------------------------------------------------
    if section == "Statements":
        st.dataframe(
            pd.DataFrame(
                supabase.table("statements").select("*").execute().data
            ),
            use_container_width=True
        )

    # --------------------------------------------------
    # USERS (EDIT + ASSIGN STOCKISTS)
    # --------------------------------------------------
    elif section == "Users":
        st.subheader("👤 Edit User & Assign Stockists")

        users = supabase.table("users") \
            .select("id, username, role, is_active") \
            .order("username") \
            .execute().data

        user = st.selectbox("Select User", users, format_func=lambda x: x["username"])

        is_active = st.checkbox("Active", value=user["is_active"])

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

            st.success("User updated successfully")

    # --------------------------------------------------
    # CREATE USER
    # --------------------------------------------------
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

            st.success("User created successfully")

    # --------------------------------------------------
    # STOCKISTS CRUD
    # --------------------------------------------------
    elif section == "Stockists":
        st.subheader("🏪 Stockists")

        name = st.text_input("New Stockist Name")

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

        stockist = st.selectbox("Select Stockist", stockists, format_func=lambda x: x["name"])
        edit_name = st.text_input("Edit Name", value=stockist["name"])

        if st.button("Save Changes"):
            supabase.table("stockists").update({
                "name": edit_name
            }).eq("id", stockist["id"]).execute()

            st.success("Stockist updated")
            st.rerun()

        if st.button("Delete Stockist"):
            used = supabase.table("statements") \
                .select("id") \
                .eq("stockist_id", stockist["id"]) \
                .limit(1) \
                .execute().data

            if used:
                st.error("Stockist in use — cannot delete")
            else:
                supabase.table("stockists") \
                    .delete() \
                    .eq("id", stockist["id"]) \
                    .execute()

                st.success("Stockist deleted")
                st.rerun()

    # --------------------------------------------------
    # PRODUCTS CRUD
    # --------------------------------------------------
    elif section == "Products":
        st.subheader("📦 Products")

        name = st.text_input("Product Name")

        peak = st.multiselect("Peak Months", list(range(1, 13)))
        high = st.multiselect("High Months", list(range(1, 13)))
        low = st.multiselect("Low Months", list(range(1, 13)))
        lowest = st.multiselect("Lowest Months", list(range(1, 13)))

        if st.button("Add Product"):
            supabase.table("products").insert({
                "name": name.strip(),
                "peak_months": peak,
                "high_months": high,
                "low_months": low,
                "lowest_months": lowest
            }).execute()

            st.success("Product added")
            st.rerun()

        st.divider()

        products = supabase.table("products") \
            .select("*") \
            .order("name") \
            .execute().data

        product = st.selectbox("Select Product", products, format_func=lambda x: x["name"])
        edit_name = st.text_input("Edit Name", value=product["name"])

        if st.button("Update Product"):
            supabase.table("products").update({
                "name": edit_name
            }).eq("id", product["id"]).execute()

            st.success("Product updated")
            st.rerun()

        if st.button("Delete Product"):
            used = supabase.table("statement_products") \
                .select("id") \
                .eq("product_id", product["id"]) \
                .limit(1) \
                .execute().data

            if used:
                st.error("Product used in statements")
            else:
                supabase.table("products").delete() \
                    .eq("id", product["id"]) \
                    .execute()

                st.success("Product deleted")
                st.rerun()

    # --------------------------------------------------
    # RESET PASSWORD
    # --------------------------------------------------
    elif section == "Reset User Password":
        users = supabase.table("users") \
            .select("id, username") \
            .execute().data

        u = st.selectbox("User", users, format_func=lambda x: x["username"])
        pwd = st.text_input("New Password", type="password")

        if st.button("Reset Password"):
            admin_supabase.auth.admin.update_user_by_id(
                u["id"],
                {"password": pwd}
            )
            st.success("Password reset successfully")

    # --------------------------------------------------
    # AUDIT LOGS
    # --------------------------------------------------
    elif section == "Audit Logs":
        logs = supabase.table("audit_logs") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute().data

        st.dataframe(pd.DataFrame(logs), use_container_width=True)

    # --------------------------------------------------
    # LOCK / UNLOCK STATEMENTS
    # --------------------------------------------------
    elif section == "Lock / Unlock Statements":
        stmts = supabase.table("statements").select("*").execute().data

        s = st.selectbox(
            "Statement",
            stmts,
            format_func=lambda x: f"{x['year']}-{x['month']} | {x['status']}"
        )

        if st.button("Lock"):
            supabase.table("statements").update({
                "status": "locked",
                "locked_at": datetime.utcnow().isoformat(),
                "locked_by": user_id
            }).eq("id", s["id"]).execute()

            st.success("Statement locked")

        if st.button("Unlock"):
            supabase.table("statements").update({
                "status": "draft"
            }).eq("id", s["id"]).execute()

            st.success("Statement unlocked")

    # --------------------------------------------------
    # ANALYTICS
    # --------------------------------------------------
    elif section == "Analytics":
        st.subheader("📊 Monthly Analytics")

        years = sorted(
            set(
                r["year"]
                for r in supabase.table("monthly_summary")
                .select("year")
                .execute().data
            )
        )

        if not years:
            st.info("No data available")
            st.stop()

        year = st.selectbox("Year", years)
        month = st.selectbox("Month", list(range(1, 13)))

        stockists = supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute().data

        stockist = st.selectbox("Stockist", stockists, format_func=lambda x: x["name"])

        rows = supabase.table("monthly_summary") \
            .select("total_issue, total_closing, total_order, products(name)") \
            .eq("year", year) \
            .eq("month", month) \
            .eq("stockist_id", stockist["id"]) \
            .execute().data

        if rows:
            df = pd.DataFrame([
                {
                    "Product": r["products"]["name"],
                    "Issue": r["total_issue"],
                    "Closing": r["total_closing"],
                    "Order": r["total_order"]
                }
                for r in rows
            ])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No data for selected period")

