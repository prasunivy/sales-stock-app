import streamlit as st
from supabase import create_client
from datetime import date

# ================= CONFIG =================
st.set_page_config(page_title="Sales & Stock App", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ================= SESSION =================
defaults = {
    "logged_in": False,
    "user": None,
    "create_statement": False,
    "statement_id": None,
    "product_index": 0,
    "product_data": {},
    "preview": False,
    "edit_product_id": None,
    "selected_stockist_id": None,
    "selected_year": None,
    "selected_month": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ================= HELPERS =================
def login(username, password):
    res = supabase.table("users").select("*") \
        .eq("username", username.strip()) \
        .eq("password", password.strip()).execute()
    if res.data:
        st.session_state.logged_in = True
        st.session_state.user = res.data[0]
        st.rerun()
    st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

def get_previous_month(year, month):
    idx = MONTHS.index(month)
    if idx == 0:
        return year - 1, MONTHS[-1]
    return year, MONTHS[idx - 1]

def last_month_data(product_id):
    """
    Stockist + Month aware last month fetch
    """
    prev_year, prev_month = get_previous_month(
        st.session_state.selected_year,
        st.session_state.selected_month
    )

    stmt = supabase.table("sales_stock_statements") \
        .select("id") \
        .eq("stockist_id", st.session_state.selected_stockist_id) \
        .eq("year", prev_year) \
        .eq("month", prev_month) \
        .order("created_at", desc=True) \
        .limit(1).execute()

    if not stmt.data:
        return {"closing": 0, "diff_closing": 0, "issue": 0}

    stmt_id = stmt.data[0]["id"]

    item = supabase.table("sales_stock_items") \
        .select("closing,diff_closing,issue") \
        .eq("statement_id", stmt_id) \
        .eq("product_id", product_id) \
        .execute()

    return item.data[0] if item.data else {"closing": 0, "diff_closing": 0, "issue": 0}

# ================= UI =================
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

        t1, t2, t3, t4 = st.tabs(
            ["👤 Users","📦 Products","🏪 Stockists","🔗 Allocation"]
        )

        # USERS
        with t1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Add User"):
                supabase.table("users").insert(
                    {"username":u,"password":p,"role":"user"}
                ).execute()
                st.rerun()

            for usr in supabase.table("users").select("*").execute().data:
                c1,c2 = st.columns([4,1])
                c1.write(f"{usr['username']} ({usr['role']})")
                if usr["role"]=="user" and c2.button("Delete", key=f"du{usr['id']}"):
                    supabase.table("users").delete().eq("id", usr["id"]).execute()
                    st.rerun()

        # PRODUCTS
        with t2:
            prod = st.text_input("Product")
            if st.button("Add Product"):
                supabase.table("products").insert({"name":prod}).execute()
                st.rerun()

            for p in supabase.table("products").select("*").order("name").execute().data:
                c1,c2 = st.columns([4,1])
                c1.write(p["name"])
                if c2.button("Delete", key=f"dp{p['id']}"):
                    supabase.table("products").delete().eq("id", p["id"]).execute()
                    st.rerun()

        # STOCKISTS
        with t3:
            stk = st.text_input("Stockist")
            if st.button("Add Stockist"):
                supabase.table("stockists").insert({"name":stk}).execute()
                st.rerun()

            for s in supabase.table("stockists").select("*").order("name").execute().data:
                c1,c2 = st.columns([4,1])
                c1.write(s["name"])
                if c2.button("Delete", key=f"ds{s['id']}"):
                    supabase.table("stockists").delete().eq("id", s["id"]).execute()
                    st.rerun()

        # ALLOCATION
        with t4:
            users = supabase.table("users").select("id,username").eq("role","user").execute().data
            stockists = supabase.table("stockists").select("id,name").execute().data

            u_map = {u["username"]:u["id"] for u in users}
            s_map = {s["name"]:s["id"] for s in stockists}

            sel_user = st.selectbox("User", list(u_map.keys()))
            sel_stk = st.multiselect("Stockists", list(s_map.keys()))

            if st.button("Allocate"):
                for s in sel_stk:
                    supabase.table("user_stockists").insert(
                        {"user_id":u_map[sel_user],"stockist_id":s_map[s]}
                    ).execute()
                st.rerun()

            st.divider()
            for a in supabase.table("user_stockists").select("id,user_id,stockist_id").execute().data:
                c1,c2 = st.columns([4,1])
                c1.write(f"User ID {a['user_id']} → Stockist ID {a['stockist_id']}")
                if c2.button("Delete", key=f"da{a['id']}"):
                    supabase.table("user_stockists").delete().eq("id", a["id"]).execute()
                    st.rerun()
