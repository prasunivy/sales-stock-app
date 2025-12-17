import streamlit as st
from supabase import create_client
from datetime import date

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Sales & Stock App", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SESSION DEFAULTS ----------------
defaults = {
    "logged_in": False,
    "user": None,
    "create_statement": False,
    "statement_id": None,
    "product_index": 0,
    "product_data": {},
    "preview": False,
    "edit_product_id": None,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------- HELPERS ----------------
def login(username, password):
    res = supabase.table("users").select("*") \
        .eq("username", username.strip()) \
        .eq("password", password.strip()).execute()
    if res.data:
        st.session_state.logged_in = True
        st.session_state.user = res.data[0]
        st.rerun()
    else:
        st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

def get_last_month_data(product_id):
    res = supabase.table("sales_stock_items") \
        .select("closing, diff_closing, issue") \
        .eq("product_id", product_id) \
        .order("created_at", desc=True) \
        .limit(1).execute()
    return res.data[0] if res.data else {"closing": 0, "diff_closing": 0, "issue": 0}

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

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
            ["👤 Users", "📦 Products", "🏪 Stockists", "🔗 Allocation"]
        )

        # USERS
        with tab1:
            u = st.text_input("New Username")
            p = st.text_input("Password", type="password")
            if st.button("Add User"):
                supabase.table("users").insert(
                    {"username": u.strip(), "password": p.strip(), "role": "user"}
                ).execute()
                st.success("User added")
                st.rerun()

            st.divider()
            for usr in supabase.table("users").select("*").execute().data:
                st.write(usr["username"], usr["role"])

        # PRODUCTS
        with tab2:
            prod = st.text_input("Product Name")
            if st.button("Add Product"):
                supabase.table("products").insert({"name": prod.strip()}).execute()
                st.success("Product added")
                st.rerun()

            st.divider()
            for p in supabase.table("products").select("*").order("name").execute().data:
                st.write(p["name"])

        # STOCKISTS
        with tab3:
            stk = st.text_input("Stockist Name")
            if st.button("Add Stockist"):
                supabase.table("stockists").insert({"name": stk.strip()}).execute()
                st.success("Stockist added")
                st.rerun()

            st.divider()
            for s in supabase.table("stockists").select("*").order("name").execute().data:
                st.write(s["name"])

        # ALLOCATION
        with tab4:
            users = supabase.table("users").select("id,username").eq("role","user").execute().data
            stockists = supabase.table("stockists").select("id,name").execute().data

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
                    st.success("Allocated")
                    st.rerun()

    # ================= USER =================
    else:
        st.header("User Dashboard")

        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True

        if st.session_state.create_statement:
            user_id = supabase.table("users").select("id") \
                .eq("username", user["username"]).execute().data[0]["id"]

            allocs = supabase.table("user_stockists").select("stockist_id") \
                .eq("user_id", user_id).execute().data

            if allocs:
                stockist_ids = [a["stockist_id"] for a in allocs]
                stockists = supabase.table("stockists").select("id,name") \
                    .in_("id", stockist_ids).execute().data
                s_map = {s["name"]: s["id"] for s in stockists}

                sel_stockist = st.selectbox("Stockist", list(s_map.keys()))
                year = st.selectbox("Year", [2023, 2024, 2025])
                month = st.selectbox("Month", MONTHS)
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
                    st.session_state.product_data = {}
                    st.success("Statement created")
