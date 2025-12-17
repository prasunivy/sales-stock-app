import streamlit as st
from supabase import create_client
from datetime import date
import urllib.parse

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
    "selected_stockist_id": None,
    "current_statement_from_date": None,
    "final_report": "",
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
    res = supabase.table("sales_stock_statements") \
        .select("id") \
        .eq("stockist_id", stockist_id) \
        .lt("from_date", current_from_date) \
        .order("from_date", desc=True) \
        .limit(1).execute()
    return res.data[0]["id"] if res.data else None

def last_month_data(product_id):
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

def build_report(stockist_name, month, year, items):
    lines = []
    lines.append(f"📦 Stock Statement")
    lines.append(f"Stockist: {stockist_name}")
    lines.append(f"Month: {month} {year}")
    lines.append("-" * 30)

    for d in items:
        order_qty = max(d["issue"] * 1.5 - d["closing"], 0)
        remarks = []

        if d["issue"] == 0 and d["closing"] > 0:
            remarks.append("No issue but stock exists")
        if d["closing"] >= 2 * d["issue"] and d["issue"] > 0:
            remarks.append("Closing stock high")
        if d["issue"] < d["prev_issue"]:
            remarks.append("Going Down")
        if d["issue"] > d["prev_issue"]:
            remarks.append("Going Up")

        lines.append(
            f"{d['name']} | O:{d['opening']} P:{d['purchase']} "
            f"I:{d['issue']} C:{d['closing']} "
            f"D:{d['diff']} | Order:{round(order_qty,1)}"
        )
        if remarks:
            lines.append("  • " + ", ".join(remarks))

    return "\n".join(lines)

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
                year = st.selectbox("Year", [2023,2024,2025])
                month = st.selectbox("Month", MONTHS)
                fd = st.date_input("From Date", date.today())
                td = st.date_input("To Date", date.today())

                if st.button("Temporary Submit"):
                    st.session_state.selected_stockist_id = s_map[sel_stockist]
                    st.session_state.current_statement_from_date = fd.isoformat()
                    st.session_state.stockist_name = sel_stockist
                    st.session_state.sel_month = month
                    st.session_state.sel_year = year

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

            p = products[st.session_state.product_index]
            last = last_month_data(p["id"])

            opening = st.number_input("Opening", value=float(last["closing"]), key=f"op_{p['id']}")
            purchase = st.number_input("Purchase", value=0.0, key=f"pur_{p['id']}")
            issue = st.number_input("Issue", value=0.0, key=f"iss_{p['id']}")
            closing = st.number_input("Closing", value=float(opening), key=f"cl_{p['id']}")

            expected = opening + purchase - issue
            diff = expected - closing

            st.session_state.product_data[p["id"]] = {
                "name": p["name"],
                "opening": opening,
                "purchase": purchase,
                "issue": issue,
                "closing": closing,
                "diff": diff,
                "prev_issue": last["issue"]
            }

            if st.button("Preview"):
                st.session_state.preview = True
                st.rerun()

        # -------- PREVIEW + FINAL SUBMIT --------
        if st.session_state.preview:
            st.header("Preview & Submit")

            rows = []
            for d in st.session_state.product_data.values():
                rows.append({
                    "Product": d["name"],
                    "Opening": d["opening"],
                    "Purchase": d["purchase"],
                    "Issue": d["issue"],
                    "Closing": d["closing"],
                    "Difference": d["diff"]
                })
            st.table(rows)

            if st.button("Final Submit"):
                for pid, d in st.session_state.product_data.items():
                    supabase.table("sales_stock_items").insert({
                        "statement_id": st.session_state.statement_id,
                        "product_id": pid,
                        "opening": d["opening"],
                        "purchase": d["purchase"],
                        "issue": d["issue"],
                        "closing": d["closing"],
                        "diff_closing": d["diff"]
                    }).execute()

                report = build_report(
                    st.session_state.stockist_name,
                    st.session_state.sel_month,
                    st.session_state.sel_year,
                    list(st.session_state.product_data.values())
                )

                st.session_state.final_report = report
                st.success("Statement submitted successfully")

        # -------- WHATSAPP --------
        if st.session_state.final_report:
            st.header("Send via WhatsApp")

            st.text_area("Report", st.session_state.final_report, height=300)

            phone = st.text_input("WhatsApp Number (with country code)", "91")
            encoded = urllib.parse.quote(st.session_state.final_report)
            wa_link = f"https://wa.me/{phone}?text={encoded}"

            st.markdown(f"[📲 Send on WhatsApp]({wa_link})", unsafe_allow_html=True)
