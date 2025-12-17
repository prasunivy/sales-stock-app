import streamlit as st
from supabase import create_client
from datetime import date

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Sales & Stock App", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SESSION ----------------
defaults = {
    "logged_in": False,
    "user": None,
    "create_statement": False,
    "statement_id": None,
    "product_index": 0,
    "product_data": {},
    "preview": False,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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

def get_last_month_data(product_id):
    res = (
        supabase.table("sales_stock_items")
        .select("opening, purchase, issue, closing")
        .eq("product_id", product_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None

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

    # ================= USER =================
    if user["role"] == "user":
        st.header("Monthly Sales & Stock Statement")

        # -------- CREATE STATEMENT --------
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

                s_map = {s["name"]: s["id"] for s in stockists}
                sel_stockist = st.selectbox("Stockist", list(s_map.keys()))
                year = st.selectbox("Year", [2024, 2025])
                month = st.selectbox("Month", ["Jan", "Feb", "Mar"])
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

        # -------- PRODUCT ENTRY --------
        if st.session_state.statement_id and not st.session_state.preview:
            products = supabase.table("products").select("id,name").order("name").execute().data
            product = products[st.session_state.product_index]

            st.subheader(f"Product: {product['name']}")

            last = get_last_month_data(product["id"]) or {}
            opening = st.number_input(
                "Opening",
                value=float(last.get("closing", 0)),
                key=f"op_{product['id']}"
            )
            purchase = st.number_input(
                "Purchase", value=0.0, key=f"pur_{product['id']}"
            )
            issue = st.number_input(
                "Issue", value=0.0, key=f"iss_{product['id']}"
            )
            closing = st.number_input(
                "Closing", value=float(opening), key=f"cl_{product['id']}"
            )

            diff = (opening + purchase - issue) - closing

            if diff != 0:
                st.warning(f"Difference in closing: {diff}")

            # SAVE TEMP DATA
            st.session_state.product_data[product["id"]] = {
                "opening": opening,
                "purchase": purchase,
                "issue": issue,
                "closing": closing,
                "diff_closing": diff,
                "product_name": product["name"],
            }

            c1, c2, c3 = st.columns(3)
            if c1.button("⬅ Previous"):
                if st.session_state.product_index > 0:
                    st.session_state.product_index -= 1
                    st.rerun()

            if c2.button("Next ➡"):
                if st.session_state.product_index < len(products) - 1:
                    st.session_state.product_index += 1
                    st.rerun()

            if c3.button("Preview"):
                st.session_state.preview = True
                st.rerun()

        # -------- PREVIEW --------
        if st.session_state.preview:
            st.header("Preview Statement")

            rows = []
            for pid, data in st.session_state.product_data.items():
                rows.append({
                    "Product": data["product_name"],
                    "Opening": data["opening"],
                    "Purchase": data["purchase"],
                    "Issue": data["issue"],
                    "Closing": data["closing"],
                    "Difference": data["diff_closing"],
                })

            st.table(rows)

            if st.button("Final Submit"):
                for pid, data in st.session_state.product_data.items():
                    supabase.table("sales_stock_items").insert({
                        "statement_id": st.session_state.statement_id,
                        "product_id": pid,
                        "opening": data["opening"],
                        "purchase": data["purchase"],
                        "issue": data["issue"],
                        "closing": data["closing"],
                        "diff_closing": data["diff_closing"],
                    }).execute()

                st.success("✅ Thank you! Statement submitted successfully.")
                st.session_state.preview = False
                st.session_state.statement_id = None
                st.session_state.product_data = {}
