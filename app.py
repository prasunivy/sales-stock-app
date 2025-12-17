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
    "edit_product_id": None
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

def last_month_data(product_id):
    res = supabase.table("sales_stock_items") \
        .select("closing, diff_closing, issue") \
        .eq("product_id", product_id) \
        .order("created_at", desc=True) \
        .limit(1).execute()
    return res.data[0] if res.data else {"closing":0,"diff_closing":0,"issue":0}

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

        with t1:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Add User"):
                supabase.table("users").insert(
                    {"username":u,"password":p,"role":"user"}
                ).execute()
                st.rerun()
            st.divider()
            for r in supabase.table("users").select("*").execute().data:
                st.write(r["username"], r["role"])

        with t2:
            prod = st.text_input("Product")
            if st.button("Add Product"):
                supabase.table("products").insert({"name":prod}).execute()
                st.rerun()
            for p in supabase.table("products").select("*").order("name").execute().data:
                st.write(p["name"])

        with t3:
            stk = st.text_input("Stockist")
            if st.button("Add Stockist"):
                supabase.table("stockists").insert({"name":stk}).execute()
                st.rerun()
            for s in supabase.table("stockists").select("*").order("name").execute().data:
                st.write(s["name"])

        with t4:
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
                            {"user_id":u_map[su],"stockist_id":s_map[s]}
                        ).execute()
                    st.rerun()

    # ================= USER =================
    else:
        st.header("User Dashboard")

        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True

        if st.session_state.create_statement:
            uid = supabase.table("users").select("id") \
                .eq("username", user["username"]).execute().data[0]["id"]

            allocs = supabase.table("user_stockists").select("stockist_id") \
                .eq("user_id", uid).execute().data

            if allocs:
                stk_ids = [a["stockist_id"] for a in allocs]
                stockists = supabase.table("stockists") \
                    .select("id,name").in_("id", stk_ids).execute().data
                s_map = {s["name"]:s["id"] for s in stockists}

                sel_stockist = st.selectbox("Stockist", list(s_map.keys()))
                year = st.selectbox("Year",[2023,2024,2025])
                month = st.selectbox("Month", MONTHS)
                fd = st.date_input("From Date", date.today())
                td = st.date_input("To Date", date.today())

                if st.button("Temporary Submit"):
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
        if st.session_state.statement_id and not st.session_state.preview:
            products = supabase.table("products").select("id,name") \
                .order("name").execute().data

            if st.session_state.edit_product_id:
                for i,p in enumerate(products):
                    if p["id"] == st.session_state.edit_product_id:
                        st.session_state.product_index = i
                st.session_state.edit_product_id = None

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

            st.session_state.product_data[p["id"]] = {
                "name":p["name"],
                "opening":opening,
                "purchase":purchase,
                "issue":issue,
                "closing":closing,
                "diff":diff,
                "prev_issue":last["issue"]
            }

            c1,c2,c3 = st.columns(3)
            if c1.button("⬅ Previous") and st.session_state.product_index>0:
                st.session_state.product_index -= 1
                st.rerun()
            if c2.button("Next ➡") and st.session_state.product_index<len(products)-1:
                st.session_state.product_index += 1
                st.rerun()
            if c3.button("Preview"):
                st.session_state.preview = True
                st.rerun()

        # -------- PREVIEW --------
        if st.session_state.preview:
            st.header("Preview Statement")
            rows = []

            for pid,d in st.session_state.product_data.items():
                order_qty = max(d["issue"]*1.5 - d["closing"], 0)
                remarks=[]
                if d["issue"]==0 and d["closing"]>0:
                    remarks.append("No issue but stock exists")
                if d["closing"]>=2*d["issue"] and d["issue"]>0:
                    remarks.append("Closing stock high")
                if d["issue"]<d["prev_issue"]:
                    remarks.append("Going Down")
                if d["issue"]>d["prev_issue"]:
                    remarks.append("Going Up")

                rows.append({
                    "Product":d["name"],
                    "Opening":d["opening"],
                    "Purchase":d["purchase"],
                    "Issue":d["issue"],
                    "Closing":d["closing"],
                    "Difference":d["diff"],
                    "Order Qty":round(order_qty,2),
                    "Remarks":", ".join(remarks)
                })

            st.table(rows)

            st.subheader("Edit Products")
            for pid,d in st.session_state.product_data.items():
                if st.button(f"Edit {d['name']}"):
                    st.session_state.edit_product_id = pid
                    st.session_state.preview = False
                    st.rerun()

            if st.button("Final Submit"):
                for pid,d in st.session_state.product_data.items():
                    supabase.table("sales_stock_items").insert({
                        "statement_id":st.session_state.statement_id,
                        "product_id":pid,
                        "opening":d["opening"],
                        "purchase":d["purchase"],
                        "issue":d["issue"],
                        "closing":d["closing"],
                        "diff_closing":d["diff"]
                    }).execute()
                st.success("✅ Thank you! Statement submitted.")
                st.session_state.clear()
