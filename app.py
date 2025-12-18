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
    "recent_view_report": "",
    "recent_view_title": "",
}
for k,v in defaults.items():
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
        return {"closing":0,"diff_closing":0,"issue":0}

    item = supabase.table("sales_stock_items") \
        .select("closing,diff_closing,issue") \
        .eq("statement_id", stmt_id) \
        .eq("product_id", product_id).execute()

    return item.data[0] if item.data else {"closing":0,"diff_closing":0,"issue":0}

def build_report(stockist, month, year, items):
    lines = [
        f"📦 Stock Statement",
        f"Stockist: {stockist}",
        f"Month: {month} {year}",
        "-"*30
    ]

    for d in items:
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

        lines.append(
            f"{d['name']} | O:{d['opening']} P:{d['purchase']} "
            f"I:{d['issue']} C:{d['closing']} D:{d['diff']} "
            f"| Order:{round(order_qty,1)}"
        )
        if remarks:
            lines.append(" • " + ", ".join(remarks))

    return "\n".join(lines)

# ================= UI =================
st.title("Sales & Stock Statement App")

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.subheader("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u,p)

# ================= DASHBOARD =================
else:
    user = st.session_state.user
    st.success(f"Logged in as {user['username']} ({user['role']})")

    if st.button("Logout"):
        logout()

    # ================= USER DASHBOARD =================
    if user["role"] == "user":
        st.header("User Dashboard")

        # ========== RECENT SUBMISSIONS SECTION ==========
        st.subheader("🕘 Recent Submissions")

        uid = user["id"]
        rec = supabase.table("sales_stock_statements") \
            .select("*") \
            .eq("user_id", uid) \
            .order("from_date", desc=True).execute().data

        if rec:
            for r in rec:
                label = f"{r['month']} {r['year']} | Stockist {r['stockist_id']}"
                if st.button(f"View Report: {label}", key=f"rec{r['id']}"):

                    items = supabase.table("sales_stock_items") \
                        .select("*,product_id") \
                        .eq("statement_id", r["id"]).execute().data

                    full = []
                    for it in items:
                        pname = supabase.table("products") \
                            .select("name").eq("id", it["product_id"]).execute().data[0]["name"]

                        full.append({
                            "name": pname,
                            "opening": it["opening"],
                            "purchase": it["purchase"],
                            "issue": it["issue"],
                            "closing": it["closing"],
                            "diff": it["diff_closing"],
                            "prev_issue": 0
                        })

                    rep = build_report("Unknown", r["month"], r["year"], full)

                    st.session_state.recent_view_report = rep
                    st.session_state.recent_view_title = label
                    st.rerun()

        if st.session_state.recent_view_report:
            st.subheader(f"Report — {st.session_state.recent_view_title}")
            st.text_area("Report", st.session_state.recent_view_report, height=300)

            phone = st.text_input("WhatsApp Number", "91")
            encoded = urllib.parse.quote(st.session_state.recent_view_report)
            st.markdown(
                f"[📲 Send WhatsApp](https://wa.me/{phone}?text={encoded})",
                unsafe_allow_html=True
            )

        st.divider()

        # ========== CREATE NEW STATEMENT BUTTON ==========
        if st.button("➕ Create New Statement"):
            st.session_state.create_statement = True
            st.rerun()

        # (existing create, entry, preview, final submit flow remains unchanged)
        # ...
        # the rest of your previous working code continues below
