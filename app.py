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
        st.error("Invalid username or password")

def logout():
    st.session_state.clear()
    st.rerun()

# ---------------- UI ----------------
st.title("Sales & Stock Statement App")

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        login(username, password)

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

        # USERS
        with tab1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")

            if st.button("Add User"):
                if u.strip() and p.strip():
                    check = supabase.table("users").select("id").eq("username", u.strip()).execute()
                    if check.data:
                        st.error("Username already exists")
                    else:
                        supabase.table("users").insert(
                            {"username": u.strip(), "password": p.strip(), "role": "user"}
                        ).execute()
                        st.rerun()

            st.divider()
            users = supabase.table("users").select("*").execute().data
            for usr in users:
                if usr["role"] == "user":
                    c1, c2 = st.columns([4,1])
                    c1.write(usr["username"])
                    if c2.button("Delete", key=usr["id"]):
                        supabase.table("users").delete().eq("id", usr["id"]).execute()
                        st.rerun()

        # PRODUCTS
        with tab2:
            prod = st.text_input("Product name")
            if st.button("Add Product"):
                if prod.strip():
                    supabase.table("products").insert({"name": prod.strip()}).execute()
                    st.rerun()

            st.divider()
            for p in supabase.table("products").select("*").order("name").execute().data:
                c1, c2 = st.columns([4,1])
                c1.write(p["name"])
                if c2.button("Delete", key=p["id"]):
                    supabase.table("products").delete().eq("id", p["id"]).execute()
                    st.rerun()

        # STOCKISTS
        with tab3:
            stk = st.text_input("Stockist name")
            if st.button("Add Stockist"):
                if stk.strip():
                    supabase.table("stockists").insert({"name": stk.strip()}).execute()
                    st.rerun()

            st.divider()
            for s in supabase.table("stockists").select("*").order("name").execute().data:
                c1, c2 = st.columns([4,1])
                c1.write(s["name"])
                if c2.button("Delete", key=s["id"]):
                    supabase.table("stockists").delete().eq("id", s["id"]).execute()
                    st.rerun()

        # ALLOCATION
        with tab4:
            users = supabase.table("users").select("id, username").eq("role","user").execute().data
            stockists = supabase.table("stockists").select("id, name").execute().data

            if users and stockists:
                u_map = {u["username"]:u["id"] for u in users}
                s_map = {s["name"]:s["id"] for s in stockists}

                sel_user = st.selectbox("User", list(u_map.keys()))
                sel_stk = st.multiselect("Stockists", list(s_map.keys()))

                if st.button("Allocate"):
                    for s in sel_stk:
                        supabase.table("user_stockists").insert(
                            {"user_id": u_map[sel_user], "stockist_id": s_map[s]}
                        ).execute()
                    st.rerun()

    # ================= USER =================
    else:
        st.header("User Dashboard")
        st.subheader("Monthly Sales & Stock Statement")

        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True

        if st.session_state.create_statement:
            user_row = supabase.table("users").select("id").eq(
                "username", user["username"]
            ).execute().data[0]

            allocs = supabase.table("user_stockists").select("stockist_id").eq(
                "user_id", user_row["id"]
            ).execute().data

            if not allocs:
                st.warning("No stockists allocated.")
            else:
                stockist_ids = [a["stockist_id"] for a in allocs]
                stockists = supabase.table("stockists").select("id, name").in_(
                    "id", stockist_ids
                ).execute().data

                stockist_map = {s["name"]: s["id"] for s in stockists}

                sel_stockist = st.selectbox("Stockist", list(stockist_map.keys()))
                year = st.selectbox("Year", [2024, 2025])
                month = st.selectbox("Month", ["Jan", "Feb", "Mar"])
                from_date = st.date_input("From Date", date.today())
                to_date = st.date_input("To Date", date.today())

                if st.button("Temporary Submit"):
                    res = supabase.table("sales_stock_statements").insert({
                        "user_id": user_row["id"],
                        "stockist_id": stockist_map[sel_stockist],
                        "year": year,
                        "month": month,
                        "from_date": from_date.isoformat(),
                        "to_date": to_date.isoformat()
                    }).execute()

                    if res.data:
                        st.session_state.statement_id = res.data[0]["id"]
                        st.session_state.product_index = 0
                        st.success("Statement created successfully ✅")

        # -------- PRODUCT NAVIGATION --------
        if st.session_state.statement_id:
            products = supabase.table("products").select("id, name").order("name").execute().data

            if products:
                product = products[st.session_state.product_index]
                st.subheader(f"Product: {product['name']}")

                c1, c2 = st.columns(2)
                if c1.button("⬅ Previous"):
                    if st.session_state.product_index > 0:
                        st.session_state.product_index -= 1
                        st.rerun()

                if c2.button("Next ➡"):
                    if st.session_state.product_index < len(products) - 1:
                        st.session_state.product_index += 1
                        st.rerun()

                st.info(f"Product {st.session_state.product_index+1} of {len(products)}")
