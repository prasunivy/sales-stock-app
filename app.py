import streamlit as st
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(
    page_title="Ivy Pharmaceuticals — Sales & Stock",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SEVERITY = {
    "High": "🔴 HIGH",
    "Medium": "🟠 MEDIUM",
    "Low": "🟡 LOW"
}

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Home",
    "statement_id": None,
    "product_index": 0,
    "view_stmt_id": None,
    "edit_stmt_id": None,
}.items():
    st.session_state.setdefault(k, v)

# ================= AUTH =================
def login(username, password):
    res = supabase.table("users") \
        .select("*") \
        .eq("username", username.strip()) \
        .eq("password", password.strip()) \
        .execute().data
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.rerun()
    st.error("Invalid credentials")

def logout():
    st.session_state.clear()
    st.rerun()

# ================= LOGIN =================
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        login(u, p)
    st.stop()

role = st.session_state.user["role"]
uid = st.session_state.user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role == "admin":
    if st.sidebar.button("📝 Data Entry"):
        st.session_state.nav = "Home"
    if st.sidebar.button("📊 Exception Dashboard"):
        st.session_state.nav = "Exceptions"
    if st.sidebar.button("🔐 Lock Control"):
        st.session_state.nav = "Lock"
    if st.sidebar.button("🤖 AI Seasonal Insights"):
        st.session_state.nav = "AI"

if role == "user":
    if st.sidebar.button("📝 New Statement"):
        st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN — LOCK CONTROL ==================
# =========================================================
if role == "admin" and st.session_state.nav == "Lock":
    st.header("🔐 Lock Control")

    stmts = supabase.table("sales_stock_statements") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute().data

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}

    for s in stmts:
        with st.container(border=True):
            st.write(f"**User:** {users.get(s['user_id'])}")
            st.write(f"**Stockist:** {stockists.get(s['stockist_id'])}")
            st.write(f"**Period:** {s['month']} {s['year']}")
            st.write(f"**Status:** {s['status']} | **Locked:** {s['locked']}")

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("Edit", key=f"edit_{s['id']}", disabled=s["locked"]):
                    st.session_state.edit_stmt_id = s["id"]
                    st.rerun()

            with c2:
                if st.button(
                    "Lock" if not s["locked"] else "Unlock",
                    key=f"lock_{s['id']}"
                ):
                    supabase.table("sales_stock_statements") \
                        .update({"locked": not s["locked"]}) \
                        .eq("id", s["id"]) \
                        .execute()
                    st.rerun()

            with c3:
                if st.button("Delete", key=f"del_{s['id']}"):
                    supabase.table("sales_stock_items") \
                        .delete() \
                        .eq("statement_id", s["id"]) \
                        .execute()
                    supabase.table("sales_stock_statements") \
                        .delete() \
                        .eq("id", s["id"]) \
                        .execute()
                    st.rerun()

# =========================================================
# ============ ADMIN — EDIT STATEMENT (PRE-LOCK) ==========
# =========================================================
if role == "admin" and st.session_state.edit_stmt_id:
    stmt = supabase.table("sales_stock_statements") \
        .select("*") \
        .eq("id", st.session_state.edit_stmt_id) \
        .execute().data[0]

    items = supabase.table("sales_stock_items") \
        .select("*") \
        .eq("statement_id", stmt["id"]) \
        .execute().data

    products = {p["id"]: p["name"] for p in supabase.table("products").select("*").execute().data}

    st.header("✏️ Edit Statement (Before Lock)")
    st.write(f"**Period:** {stmt['month']} {stmt['year']}")

    for i in items:
        st.subheader(products.get(i["product_id"]))
        opening = i["opening"]

        purchase = st.number_input(
            "Purchase", value=i["purchase"], key=f"p{i['id']}"
        )
        issue = st.number_input(
            "Issue", value=i["issue"], key=f"i{i['id']}"
        )
        closing = st.number_input(
            "Closing", value=i["closing"], key=f"c{i['id']}"
        )

        diff = opening + purchase - issue - closing
        st.write(f"Difference: {diff}")

        supabase.table("sales_stock_items").update({
            "purchase": purchase,
            "issue": issue,
            "closing": closing,
            "difference": diff
        }).eq("id", i["id"]).execute()

    if st.button("⬅ Back to Lock Control"):
        st.session_state.edit_stmt_id = None
        st.rerun()

# =========================================================
# ================= ADMIN — EXCEPTIONS ====================
# =========================================================
if role == "admin" and st.session_state.nav == "Exceptions":
    st.header("🚨 Exception Dashboard (Read-Only)")

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data
    products = {p["id"]: p["name"] for p in supabase.table("products").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}

    for i in items:
        stmt = next((s for s in stmts if s["id"] == i["statement_id"]), None)
        if not stmt:
            continue

        severity = None
        if i["difference"] != 0:
            severity = "High"
        elif i["issue"] == 0 and i["closing"] > 0:
            severity = "Medium"
        elif i["closing"] >= 2 * i["issue"] and i["issue"] > 0:
            severity = "Low"

        if not severity:
            continue

        with st.container(border=True):
            st.markdown(f"### {SEVERITY[severity]} — {products.get(i['product_id'])}")
            st.write(f"{stmt['month']} {stmt['year']} | {stockists.get(stmt['stockist_id'])}")
            st.write(f"Issue: {i['issue']} | Closing: {i['closing']} | Diff: {i['difference']}")

st.write("---")
st.write("© Ivy Pharmaceuticals")
