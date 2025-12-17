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
    "current_statement_from_date": None,
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

def get_last_statement(stockist_id, current_from_date):
    """
    Get the immediately previous statement for this stockist
    based on from_date (robust, month-independent)
    """
    res = supabase.table("sales_stock_statements") \
        .select("id") \
        .eq("stockist_id", stockist_id) \
        .lt("from_date", current_from_date) \
        .order("from_date", desc=True) \
        .limit(1).execute()
    return res.data[0]["id"] if res.data else None

def last_month_data(product_id):
    """
    Fetch last month's product data based on previous statement
    """
    stmt_id = get_last_statement(
        st.session_state.selected_stockist_id,
        st.session_state.current_statement_from_date
    )

    if not stmt_id:
        return {"closing": 0, "diff_closing": 0, "issue": 0}

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

    # ================= USER =================
    if user["role"] == "user":
        st.header("User Dashboard")

        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True

        # -------- STATEMENT HEADER --------
        if st.session_state.create_statement and not st.session_state.statement_id:
            uid = supabase.table("users").select("id") \
                .eq("username", user["username"]).execute().data[0]["id"]

            allocs = supabase.table("user_stockists").select("stockist_id") \
                .eq("user_id", uid).execute().data

            if not allocs:
                st.warning("No stockist allocated.")
            else:
                stk_ids = [a["stockist_id"] for a in allocs]
                stockists = supabase.table("stockists") \
                    .select("id,name").in_("id", stk_ids).execute().data
                s_map = {s["name"]: s["id"] for s in stockists}

                sel_stockist = st.selectbox("Stockist", list(s_map.keys()))
                year = st.selectbox("Year", [2023, 2024, 2025])
                month = st.selectbox("Month", MONTHS)
                fd = st.date_input("From Date", date.today())
                td = st.date_input("To Date", date.today())

                if st.button("Temporary Submit"):
                    st.session_state.selected_stockist_id = s_map[sel_stockist]
                    st.session_state.current_statement_from_date = fd.isoformat()

                    res = supabase.table("sales_stock_statements").insert({
                        "user_id": uid,
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
            if c2.button("Next ➡") and st.session_state.product_index < len(products) - 1:
                st.session_state.product_index += 1
                st.rerun()
