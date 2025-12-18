import streamlit as st
from supabase import create_client
from datetime import date
import urllib.parse
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(page_title="Sales & Stock App", layout="wide")
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTHS = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]

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
        .order("from_date", desc=True).limit(1).execute()
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
        order_qty = max(int(d["issue"] * 1.5 - d["closing"]), 0)

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
            f"I:{d['issue']} C:{d['closing']} D:{d['diff']} | Order:{order_qty}"
        )
        if remarks:
            lines.append(" • " + ", ".join(remarks))

    return "\n".join(lines)


def generate_pdf(text):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    for line in text.split("\n"):
        c.drawString(40, y, line)
        y -= 15
        if y <= 40:
            c.showPage()
            y = height - 40
    c.save()
    buffer.seek(0)
    return buffer


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

    # ================= ADMIN DASHBOARD =================
    if user["role"] == "admin":
        st.header("Admin Dashboard")
        st.subheader("⬇ Export Data")

        # SUMMARY CSV
        if st.button("Download Statements Summary CSV"):
            data = supabase.table("sales_stock_statements").select("*").execute().data
            out=[]
            for r in data:
                u=supabase.table("users").select("username").eq("id",r["user_id"]).execute()
                s=supabase.table("stockists").select("name").eq("id",r["stockist_id"]).execute()
                out.append({
                    "statement_id": r["id"],
                    "username": u.data[0]["username"] if u.data else "Unknown",
                    "stockist": s.data[0]["name"] if s.data else "Unknown",
                    "from_date": r["from_date"],
                    "to_date": r["to_date"],
                    "month": r["month"],
                    "year": r["year"]
                })
            df = pd.DataFrame(out)
            st.download_button("Download Summary CSV", df.to_csv(index=False), "summary.csv")

        # DETAILED CSV
        if st.button("Download Item Details CSV"):
            items = supabase.table("sales_stock_items").select("*").execute().data
            out=[]
            for it in items:
                stmt = supabase.table("sales_stock_statements").select("*") \
                    .eq("id", it["statement_id"]).execute().data[0]

                u=supabase.table("users").select("username").eq("id",stmt["user_id"]).execute().data
                s=supabase.table("stockists").select("name").eq("id",stmt["stockist_id"]).execute().data
                p=supabase.table("products").select("name").eq("id",it["product_id"]).execute().data

                out.append({
                    "statement_id": it["statement_id"],
                    "username": u[0]["username"] if u else "Unknown",
                    "stockist": s[0]["name"] if s else "Unknown",
                    "from_date": stmt["from_date"],
                    "to_date": stmt["to_date"],
                    "month": stmt["month"],
                    "year": stmt["year"],
                    "product": p[0]["name"] if p else "Unknown",
                    "opening": it["opening"],
                    "purchase": it["purchase"],
                    "issue": it["issue"],
                    "closing": it["closing"],
                    "difference": it["diff_closing"],
                })
            df = pd.DataFrame(out)
            st.download_button("Download Detailed CSV", df.to_csv(index=False), "items.csv")

        st.subheader("📄 Export Statements as PDF")
        data = supabase.table("sales_stock_statements").select("*").execute().data
        for r in data:
            s = supabase.table("stockists").select("name").eq("id", r["stockist_id"]).execute().data
            stock = s[0]["name"] if s else "Unknown"
            label = f"{r['month']} {r['year']} | {stock}"
            if st.button(f"PDF: {label}", key=f"adm_pdf{r['id']}"):
                items = supabase.table("sales_stock_items").select("*").eq("statement_id", r["id"]).execute().data
                full=[]
                for it in items:
                    pname = supabase.table("products").select("name") \
                        .eq("id", it["product_id"]).execute().data
                    full.append({
                        "name": pname[0]["name"] if pname else "Unknown",
                        "opening": it["opening"],
                        "purchase": it["purchase"],
                        "issue": it["issue"],
                        "closing": it["closing"],
                        "diff": it["diff_closing"],
                        "prev_issue": 0
                    })
                rep = build_report(stock, r["month"], r["year"], full)
                pdf = generate_pdf(rep)
                st.download_button("Download PDF", pdf, f"{stock}_{r['month']}_{r['year']}.pdf")

        st.subheader("📊 Territory Analytics Dashboard")

        # ---- Product-wise Trend (last 3 months)
        st.markdown("### 📦 Product-wise Issue Trend (Last 3 Months)")
        stmts = supabase.table("sales_stock_statements").select("*").execute().data
        items = supabase.table("sales_stock_items").select("*").execute().data
        products = supabase.table("products").select("*").execute().data

        # last 3 months
        last3 = pd.DataFrame(stmts).tail(3)
        prod_totals = {}
        for stmt in last3.to_dict("records"):
            sid = stmt["id"]
            for it in items:
                if it["statement_id"] == sid:
                    pid = it["product_id"]
                    prod_totals[pid] = prod_totals.get(pid,0) + it["issue"]

        if prod_totals:
            labels = []
            values = []
            for pid,val in prod_totals.items():
                name = next((p["name"] for p in products if p["id"]==pid), "Unknown")
                labels.append(name)
                values.append(int(val))

            fig=plt.figure()
            plt.bar(labels, values)
            plt.title("Product Trend")
            plt.xlabel("Products")
            plt.ylabel("Issue Qty")
            st.pyplot(fig)

        # ---- Stockist Trend
        st.markdown("### 🏪 Stockist-wise Issue Distribution")
        stock_totals = {}
        for it in items:
            stmt = next((s for s in stmts if s["id"] == it["statement_id"]), None)
            if stmt:
                stock_totals[stmt["stockist_id"]] = stock_totals.get(stmt["stockist_id"],0) + it["issue"]

        if stock_totals:
            labels=[]
            values=[]
            for sid,val in stock_totals.items():
                s = next((st for st in supabase.table("stockists").select("*").execute().data if st["id"]==sid),None)
                labels.append(s["name"] if s else "Unknown")
                values.append(int(val))

            fig=plt.figure()
            plt.bar(labels, values)
            plt.title("Stockist Trend")
            plt.xlabel("Stockists")
            plt.ylabel("Issue Qty")
            st.pyplot(fig)

        # ---- User Submissions Trend
        st.markdown("### 👤 User Submission Count")
        submissions = {}
        for s in stmts:
            submissions[s["user_id"]] = submissions.get(s["user_id"],0) + 1

        if submissions:
            labels=[]
            values=[]
            users = supabase.table("users").select("*").execute().data
            for uid,count in submissions.items():
                uname = next((u["username"] for u in users if u["id"]==uid), "Unknown")
                labels.append(uname)
                values.append(int(count))

            fig=plt.figure()
            plt.bar(labels, values)
            plt.title("User Submissions")
            plt.xlabel("Users")
            plt.ylabel("Count")
            st.pyplot(fig)



    # ================= USER DASHBOARD =================
    else:
        st.header("User Dashboard")

        # (USER SECTION UNCHANGED — SAME AS PRIOR VERSION)
        # (CONTAINS Create Statement, Product Entry, Preview, Final Submission, Recent Submission, PDF, WhatsApp)
        ...
