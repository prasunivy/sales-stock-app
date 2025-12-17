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
    else:
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
    if not all([
        st.session_state.selected_stockist_id,
        st.session_state.selected_year,
        st.session_state.selected_month
    ]):
        return {"closing": 0, "diff_closing": 0, "issue": 0}

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

        tab1, tab2, tab3, tab4 = st.tabs(
            ["👤 Users", "📦 Products", "🏪 Stockists", "🔗 Allocation"]
        )

        with tab1:
            u = st.text_input("New Username")
            p = st.text_input("Password", type="password")
            if st.button("Add User"):
                supabase.table("users").insert(
                    {"username": u, "password": p, "role": "user"}
                ).execute()
                st.rerun()

            for usr in supabase.table("users").select("*").execute().data:
                c1, c2 = st.columns([4, 1])
                c1.write(f"{usr['username']} ({usr['role']})")
                if usr["role"] == "user" and c2.button("Delete", key=f"u{usr['id']}"):
                    supabase.table("users").delete().eq("id", usr["id"]).execute()
                    st.rerun()

        with tab2:
            prod = st.text_input("Product")
            if st.button("Add Product"):
                supabase.table("products").insert({"name": prod}).execute()
                st.rerun()

            for p in supabase.table("products").select("*").order("name").execute().data:
                c1, c2 = st.columns([4, 1])
                c1.write(p["name"])
                if c2.button("Delete", key=f"p{p['id']}"):
                    supabase.table("products").delete().eq("id", p["id"]).execute()
                    st.rerun()

        with tab3:
            stk = st.text_input("Stockist")
            if st.button("Add Stockist"):
                supabase.table("stockists").insert({"name": stk}).execute()
                st.rerun()

            for s in supabase.table("stockists").select("*").order("name").execute().data:
                c1, c2 = st.columns([4, 1])
                c1.write(s["name"])
                if c2.button("Delete", key=f"s{s['id']}"):
                    supabase.table("stockists").delete().eq("id", s["id"]).execute()
                    st.rerun()

        with tab4:
            users = supabase.table("users").select("id,username").eq("role","user").execute().data
            stockists = supabase.table("stockists").select("id,name").execute().data

            u_map = {u["username"]:u["id"] for u in users}
            s_map = {s["name"]:s["id"] for s in stockists}

            su = st.selectbox("User", list(u_map.keys()))
            ss = st.multiselect("Stockists", list(s_map.keys()))

            if st.button("Allocate"):
                for s in ss:
                    supabase.table("user_stockists").insert(
                        {"user_id":u_map[su],"stockist_id":s_map[s]}
                    ).execute()
                st.rerun()

    # ================= USER =================
    else:
        st.header("User Dashboard")

        # ALWAYS SHOW THIS BUTTON
        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True

        # -------- STATEMENT HEADER --------
        if st.session_state.create_statement and not st.session_state.statement_id:
            uid = supabase.table("users").select("id") \
                .eq("username", user["username"]).execute().data[0]["id"]

            allocs = supabase.table("user_stockists").select("stockist_id") \
                .eq("user_id", uid).execute().data

            if not allocs:
                st.warning("No stockist allocated to you.")
            else:
                stk_ids = [a["stockist_id"] for a in allocs]
                stockists = supabase.table("stockists") \
                    .select("id,name").in_("id", stk_ids).execute().data
                s_map = {s["name"]:s["id"] for s in stockists}

                sel_stockist = st.selectbox("Stockist", list(s_map.keys()))
                year = st.selectbox("Year", [2023,2024,2025])
                month = st.selectbox("Month", MONTHS)
                fd = st.date_input("From Date", date.today())
                td = st.date_input("To Date", date.today())

                if st.button("Temporary Submit"):
                    st.session_state.selected_stockist_id = s_map[sel_stockist]
                    st.session_state.selected_year = year
                    st.session_state.selected_month = month

                    res = supabase.table("sales_stock_statements").insert({
                        "user_id":uid,
                        "stockist_id":s_map[sel_stockist],
                        "year":year,
                        "month":month,
                        "from_date":fd.isoformat(),
                        "to_date":td.isoformat()
                    }).execute()

                    st.session_state.statement_id = res.data[0]["id"]
                    st.session_state.product_index = 0
                    st.session_state.product_data = {}
                    st.success("Statement created")

        # -------- PRODUCT ENTRY --------
        if st.session_state.statement_id:
            products = supabase.table("products").select("id,name") \
                .order("name").execute().data

            p = products[st.session_state.product_index]
            last = last_month_data(p["id"])

            st.subheader(f"Product: {p['name']}")
            st.markdown(
                f"**Last Month Closing:** {last['closing']}  \n"
                f"**Last Month Difference:** {last['diff_closing']}"
            )

            opening = st.number_input("Opening", value=float(last["closing"]), key=f"op_{p['id']}")
            purchase = st.number_input("Purchase", value=0.0, key=f"pur_{p['id']}")
            issue = st.number_input("Issue", value=0.0, key=f"iss_{p['id']}")
            closing = st.number_input("Closing (Physical)", value=float(opening), key=f"cl_{p['id']}")

            expected = opening + purchase - issue
            diff = expected - closing

            if diff != 0:
                st.warning(f"Difference in Closing: {diff}")
            else:
                st.success("Closing matched")

            c1, c2 = st.columns(2)
            if c1.button("⬅ Previous") and st.session_state.product_index > 0:
                st.session_state.product_index -= 1
                st.rerun()
            if c2.button("Next ➡") and st.session_state.product_index < len(products)-1:
                st.session_state.product_index += 1
                st.rerun()
