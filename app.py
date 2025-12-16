import streamlit as st
from supabase import create_client
from datetime import date

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Sales & Stock App", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SESSION INIT ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.create_statement = False
    st.session_state.statement_id = None

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

        # ---------- USERS ----------
        with tab1:
            st.subheader("Add User")
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")

            if st.button("Add User"):
                if not u or not p:
                    st.error("Username and password required")
                else:
                    check = supabase.table("users").select("id").eq("username", u.strip()).execute()
                    if check.data:
                        st.error("Username already exists")
                    else:
                        supabase.table("users").insert(
                            {"username": u.strip(), "password": p.strip(), "role": "user"}
                        ).execute()
                        st.success("User added")
                        st.rerun()

            st.divider()
            users = supabase.table("users").select("*").execute().data
            for usr in users:
                if usr["role"] == "user":
                    c1, c2 = st.columns([4, 1])
                    c1.write(usr["username"])
                    if c2.button("Delete", key=usr["id"]):
                        supabase.table("users").delete().eq("id", usr["id"]).execute()
                        st.rerun()

        # ---------- PRODUCTS ----------
        with tab2:
            st.subheader("Add Product")
            prod = st.text_input("Product name")

            if st.button("Add Product"):
                if prod:
                    supabase.table("products").insert({"name": prod.strip()}).execute()
                    st.rerun()

            st.divider()
            products = supabase.table("products").select("*").order("name").execute().data
            for p in products:
                c1, c2 = st.columns([4, 1])
                c1.write(p["name"])
                if c2.button("Delete", key=p["id"]):
                    supabase.table("products").delete().eq("id", p["id"]).execute()
                    st.rerun()

        # ---------- STOCKISTS ----------
        with tab3:
            st.subheader("Add Stockist")
            stk = st.text_input("Stockist name")

            if st.button("Add Stockist"):
                if stk:
                    supabase.table("stockists").insert({"name": stk.strip()}).execute()
                    st.rerun()

            st.divider()
            stockists = supabase.table("stockists").select("*").order("name").execute().data
            for s in stockists:
                c1, c2 = st.columns([4, 1])
                c1.write(s["name"])
                if c2.button("Delete", key=s["id"]):
                    supabase.table("stockists").delete().eq("id", s["id"]).execute()
                    st.rerun()

        # ---------- ALLOCATION ----------
        with tab4:
            st.subheader("Allocate Stockists to Users")

            users = supabase.table("users").select("id, username").eq("role", "user").execute().data
            stockists = supabase.table("stockists").select("id, name").execute().data

            if users and stockists:
                user_map = {u["username"]: u["id"] for u in users}
                stk_map = {s["name"]: s["id"] for s in stockists}

                sel_user = st.selectbox("User", list(user_map.keys()))
                sel_stk = st.multiselect("Stockists", list(stk_map.keys()))

                if st.button("Allocate"):
                    for s in sel_stk:
                        supabase.table("user_stockists").insert(
                            {"user_id": user_map[sel_user], "stockist_id": stk_map[s]}
                        ).execute()
                    st.success("Allocated")
                    st.rerun()

            st.divider()
            allocs = supabase.table("user_stockists").select("*").execute().data
            for a in allocs:
                u = supabase.table("users").select("username").eq("id", a["user_id"]).execute().data[0]
                s = supabase.table("stockists").select("name").eq("id", a["stockist_id"]).execute().data[0]
                st.write(f"{u['username']} → {s['name']}")

    # ================= USER =================
    else:
        st.header("User Dashboard")
        st.subheader("Monthly Sales & Stock Statement")

        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True

        if st.session_state.create_statement:
            # get user id
            user_row = supabase.table("users").select("id").eq(
                "username", user["username"]
            ).execute().data[0]

            # allocated stockists
            allocs = supabase.table("user_stockists").select("stockist_id").eq(
                "user_id", user_row["id"]
            ).execute().data

            if not allocs:
                st.warning("No stockists allocated to you.")
            else:
                stockist_ids = [a["stockist_id"] for a in allocs]
                stockists = supabase.table("stockists").select("id, name").in_(
                    "id", stockist_ids
                ).execute().data

                stockist_map = {s["name"]: s["id"] for s in stockists}

                sel_stockist = st.selectbox("Select Stockist", list(stockist_map.keys()))
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
                        "from_date": from_date,
                        "to_date": to_date
                    }).execute()

                    if res.data:
                        st.success("Statement created successfully ✅")
                        st.session_state.statement_id = res.data[0]["id"]
                    else:
                        st.error("Failed to create statement")
