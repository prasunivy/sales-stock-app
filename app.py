import streamlit as st
from supabase import create_client
from datetime import datetime, timedelta
import csv, io
from fpdf import FPDF

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SEVERITY_RANK = {"High": 1, "Medium": 2, "Low": 3}
SEVERITY_BADGE = {
    "High": "🔴 HIGH",
    "Medium": "🟠 MEDIUM",
    "Low": "🟡 LOW"
}

# ================= HELPERS =================
def safe_pdf_text(text):
    if text is None:
        return ""
    return (
        str(text)
        .replace("≥", ">=")
        .replace("×", "x")
        .replace("–", "-")
        .replace("—", "-")
        .encode("latin-1", "ignore")
        .decode("latin-1")
    )

# ================= SESSION =================
for k, v in {
    "logged_in": False,
    "user": None,
    "nav": "Exception Dashboard",
    "edit_statement_id": None,
    "refresh": 0
}.items():
    st.session_state.setdefault(k, v)

# ================= AUTH =================
def login(u, p):
    res = supabase.table("users").select("*") \
        .eq("username", u.strip()).eq("password", p.strip()).execute().data
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

# ================= SIDEBAR =================
st.sidebar.title("Menu")
if role == "admin":
    if st.sidebar.button("Exception Dashboard"):
        st.session_state.nav = "Exception Dashboard"
    if st.sidebar.button("Lock Control"):
        st.session_state.nav = "Lock Control"
if st.sidebar.button("Logout"):
    logout()

# =========================================================
# ================= ADMIN EDIT / VIEW =====================
# =========================================================
if role == "admin" and st.session_state.edit_statement_id:
    stmt = supabase.table("sales_stock_statements") \
        .select("*") \
        .eq("id", st.session_state.edit_statement_id) \
        .execute().data[0]

    items = supabase.table("sales_stock_items") \
        .select("*") \
        .eq("statement_id", stmt["id"]) \
        .execute().data

    products = {p["id"]: p["name"] for p in supabase.table("products").select("*").execute().data}

    st.header("📄 Statement Detail")
    st.write(f"**Period:** {stmt['month']} {stmt['year']}")
    st.write(f"**Status:** {'Locked (Read-only)' if stmt['locked'] else 'Open (Editable)'}")
    st.write("---")

    updated = []

    for i in items:
        st.subheader(products.get(i["product_id"], "Unknown"))
        opening = i["opening"]
        purchase = st.number_input("Purchase", value=i["purchase"], key=f"p_{i['id']}", disabled=stmt["locked"])
        issue = st.number_input("Issue", value=i["issue"], key=f"i_{i['id']}", disabled=stmt["locked"])
        closing = st.number_input("Closing", value=i["closing"], key=f"c_{i['id']}", disabled=stmt["locked"])
        diff = opening + purchase - issue - closing
        st.write(f"Difference: {diff}")
        updated.append((i["id"], purchase, issue, closing, diff))

    if not stmt["locked"] and st.button("Save Changes"):
        for uid, p, iss, c, d in updated:
            supabase.table("sales_stock_items").update({
                "purchase": p,
                "issue": iss,
                "closing": c,
                "difference": d
            }).eq("id", uid).execute()
        st.success("Changes saved")
        st.session_state.edit_statement_id = None
        st.rerun()

    if st.button("⬅ Back to Dashboard"):
        st.session_state.edit_statement_id = None
        st.rerun()

    st.stop()

# =========================================================
# ================= LOCK CONTROL ==========================
# =========================================================
if role == "admin" and st.session_state.nav == "Lock Control":
    st.header("🔐 Lock Control")

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements") \
        .select("*").order("created_at", desc=True).execute().data

    for s in stmts:
        with st.container(border=True):
            st.write(f"**User:** {users.get(s['user_id'], 'Unknown')}")
            st.write(f"**Stockist:** {stockists.get(s['stockist_id'], 'Unknown')}")
            st.write(f"**Period:** {s['month']} {s['year']}")
            st.write(f"**Status:** {'Locked' if s['locked'] else 'Open'}")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.button("Edit", key=f"edit_{s['id']}", disabled=s["locked"])
            with c2:
                st.button("Delete", key=f"del_{s['id']}", disabled=s["locked"])
            with c3:
                st.button("Unlock" if s["locked"] else "Lock", key=f"lock_{s['id']}")

# =========================================================
# ============ EXCEPTION DASHBOARD (BADGES) ===============
# =========================================================
if role == "admin" and st.session_state.nav == "Exception Dashboard":
    st.header("🚨 Exception Dashboard")

    users = {u["id"]: u["username"] for u in supabase.table("users").select("*").execute().data}
    stockists = {s["id"]: s["name"] for s in supabase.table("stockists").select("*").execute().data}

    stmts = supabase.table("sales_stock_statements").select("*").execute().data
    today = datetime.utcnow()

    st.subheader("📄 Statement Exceptions")

    for s in stmts:
        created = datetime.fromisoformat(s["created_at"].replace("Z", ""))

        severity = None
        reason = None

        if s["status"] == "draft" and today - created > timedelta(days=3):
            severity = "High"
            reason = "Draft > 3 Days"
        elif s["status"] == "final" and not s["locked"]:
            severity = "Medium"
            reason = "Final but Not Locked"
        elif s["status"] == "final" and s["locked"]:
            severity = "Low"
            reason = "Locked Final (Review)"

        if severity:
            with st.container(border=True):
                st.markdown(f"### {SEVERITY_BADGE[severity]}")
                st.write(f"**User:** {users.get(s['user_id'], 'Unknown')}")
                st.write(f"**Stockist:** {stockists.get(s['stockist_id'], 'Unknown')}")
                st.write(f"**Period:** {s['month']} {s['year']}")
                st.write(f"**Reason:** {reason}")
                st.write(f"**Status:** {'Locked' if s['locked'] else 'Open'}")

                if st.button("Open Statement", key=f"open_{s['id']}"):
                    st.session_state.edit_statement_id = s["id"]
                    st.rerun()

st.write("---")
st.write("© Ivy Pharmaceuticals")
