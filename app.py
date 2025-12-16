import streamlit as st
from supabase import create_client
from datetime import date

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Sales & Stock App", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.create_statement = False
    st.session_state.statement_id = None
    st.session_state.product_index = 0

# ---------------- FUNCTIONS ----------------
def login(username, password):
    res = (
        supabase.table("users")
        .select("*")
        .eq("username", username.strip())
        .eq("password", password.strip())
        .execute()
    )
    if res.data:
        st.session_state.logged_in = True
        st.session_state.user = res.data[0]
        st.rerun()
    else:
        st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

def get_last_month_data(stockist_id, product_id):
    res = (
        supabase.table("sales_stock_items")
        .select("issue, closing")
        .eq("stockist_id", stockist_id)
        .eq("product_id", product_id)
        .order("created_at", desc=True)
        .limit(2)
        .execute()
    )
    return res.data if res.data else []

# ---------------- UI ----------------
st.title("Sales & Stock Statement App")

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.subheader("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u, p)

# ================= DASHBOARD =================
else:
    user = st.session_state.user
    st.success(f"Logged in as {user['username']} ({user['role']})")

    if st.button("Logout"):
        logout()

    # ================= ADMIN =================
    if user["role"] == "admin":
        st.header("Admin Dashboard")

        tab1, tab2, tab3, tab4 = st.tabs(
            ["👤 Users", "📦 Products", "🏪 Stockists", "🔗 Allocate Stockists"]
        )

        with tab1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Add User"):
                if u.strip() and p.strip():
                    supabase.table("users").insert(
                        {"username": u.strip(), "password": p.strip(), "role": "user"}
                    ).execute()
                    st.rerun()

        with tab2:
            prod = st.text_input("Product")
            if st.button("Add Product"):
                if prod.strip():
                    supabase.table("products").insert({"name": prod.strip()}).execute()
                    st.rerun()

        with tab3:
            stk = st.text_input("Stockist")
            if st.button("Add Stockist"):
                if stk.strip():
                    supabase.table("stockists").insert({"name": stk.strip()}).execute()
                    st.rerun()

        with tab4:
            users = supabase.table("users").select("id,username").eq("role","user").execute().data
            stockists = supabase.table("stockists").select("id,name").execute().data
            if users and stockists:
                u_map = {u["username"]:u["id"] for u in users}
                s_map = {s["name"]:s["id"] for s in stockists}
                su = st.selectbox("User", list(u_map.keys()))
                ss = st.multiselect("Stockists", list(s_map.keys()))
                if st.button("Allocate"):
                    for s in ss:
                        supabase.table("user_stockists").insert(
                            {"user_id": u_map[su], "stockist_id": s_map[s]}
                        ).execute()
                    st.rerun()

    # ================= USER =================
    else:
        st.header("User Dashboard")

        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True

        if st.session_state.create_statement:
            user_id = supabase.table("users").select("id").eq(
                "username", user["username"]
            ).execute().data[0]["id"]

            allocs = supabase.table("user_stockists").select("stockist_id").eq(
                "user_id", user_id
            ).execute().data

            if allocs:
                stockist_ids = [a["stockist_id"] for a in allocs]
                stockists = supabase.table("stockists").select("id,name").in_(
                    "id", stockist_ids
                ).execute().data
                s_map = {s["name"]:s["id"] for s in stockists}

                sel_stockist = st.selectbox("Stockist", list(s_map.keys()))
                year = st.selectbox("Year", [2024,2025])
                month = st.selectbox("Month", ["Jan","Feb","Mar"])
                fd = st.date_input("From Date", date.today())
                td = st.date_input("To Date", date.today())

                if st.button("Temporary Submit"):
                    res = supabase.table("sales_stock_statements").insert({
                        "user_id": user_id,
                        "stockist_id": s_map[sel_stockist],
                        "year": year,
                        "month": month,
                        "from_date": fd.isoformat(),
                        "to_date": td.isoformat()
                    }).execute()
                    st.session_state.statement_id = res.data[0]["id"]
                    st.session_state.product_index = 0

        # -------- PRODUCT ENTRY --------
        if st.session_state.statement_id:
            products = supabase.table("products").select("id,name").order("name").execute().data
            product = products[st.session_state.product_index]

            st.subheader(f"Product: {product['name']}")

            last_data = get_last_month_data(
                s_map[sel_stockist], product["id"]
            )

            last_closing = last_data[0]["closing"] if last_data else 0
            last_issues = [d["issue"] for d in last_data]

            opening = st.number_input(
                "Opening", value=float(last_closing), step=1.0,
                key=f"op_{product['id']}"
            )
            purchase = st.number_input(
                "Purchase", step=1.0, key=f"pur_{product['id']}"
            )
            issue = st.number_input(
                "Issue", step=1.0, key=f"iss_{product['id']}"
            )
            closing = st.number_input(
                "Closing", value=float(opening + purchase - issue),
                step=1.0, key=f"cl_{product['id']}"
            )

            diff = opening + purchase - issue - closing
            st.info(f"Difference in Closing: {diff}")

            if last_issues:
                avg_issue = sum(last_issues) / len(last_issues)
                if issue < avg_issue:
                    st.warning("📉 Going Down")
                elif issue > last_issues[0]:
                    st.success("📈 Going Up")

            c1, c2 = st.columns(2)
            if c1.button("⬅ Previous"):
                if st.session_state.product_index > 0:
                    st.session_state.product_index -= 1
                    st.rerun()

            if c2.button("Next ➡"):
                if st.session_state.product_index < len(products) - 1:
                    st.session_state.product_index += 1
                    st.rerun()
