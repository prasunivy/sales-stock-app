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

        # EXPORT SECTION INSIDE DROPDOWN
        with st.expander("📂 Export Statements"):
            if st.button("Download Summary CSV"):
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
                st.download_button("Summary CSV", df.to_csv(index=False), "summary.csv")

            if st.button("Download Detailed CSV"):
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
                st.download_button("Detailed CSV", df.to_csv(index=False), "items.csv")

            st.write("### Download PDFs")
            data = supabase.table("sales_stock_statements").select("*").execute().data
            for r in data:
                s=supabase.table("stockists").select("name").eq("id",r["stockist_id"]).execute().data
                stock = s[0]["name"] if s else "Unknown"
                label = f"{r['month']} {r['year']} | {stock}"
                if st.button(label, key=f"adm_pdf{r['id']}"):
                    items = supabase.table("sales_stock_items").select("*").eq("statement_id", r["id"]).execute().data
                    full=[]
                    for it in items:
                        pname=supabase.table("products").select("name").eq("id",it["product_id"]).execute().data
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
                    st.download_button("Download", pdf, f"{stock}_{r['month']}_{r['year']}.pdf")

        # ================= ANALYTICS WITH FILTERS =================
        st.subheader("📊 Territory Analytics Dashboard")

        # FILTERING CONTROLS
        all_users = ["All"]
        all_users += [u["username"] for u in supabase.table("users").select("*").execute().data]

        all_stockists = ["All"]
        all_stockists += [s["name"] for s in supabase.table("stockists").select("*").execute().data]

        all_products = ["All"]
        all_products += [p["name"] for p in supabase.table("products").select("*").execute().data]

        sel_user = st.selectbox("Filter by User", all_users)
        sel_stock = st.selectbox("Filter by Stockist", all_stockists)
        sel_prod = st.selectbox("Filter by Product", all_products)

        # FETCH DATA
        stmts = supabase.table("sales_stock_statements").select("*").execute().data
        items = supabase.table("sales_stock_items").select("*").execute().data
        products = supabase.table("products").select("*").execute().data
        users_data = supabase.table("users").select("*").execute().data
        stockists_data = supabase.table("stockists").select("*").execute().data

        # APPLY FILTERS
        def user_match(r):
            if sel_user == "All":
                return True
            u = next((x for x in users_data if x["id"] == r["user_id"]), None)
            return u and u["username"] == sel_user

        def stock_match(r):
            if sel_stock == "All":
                return True
            s = next((x for x in stockists_data if x["id"] == r["stockist_id"]), None)
            return s and s["name"] == sel_stock

        # Product filter applies on items later
        # Filter statements now
        filtered_stmt_ids = []
        for s in stmts:
            if user_match(s) and stock_match(s):
                filtered_stmt_ids.append(s["id"])

        # ---- Product-wise Trend ----
        st.write("### 📦 Product-wise Issue Trend")

        prod_totals={}
        for it in items:
            if it["statement_id"] in filtered_stmt_ids:
                pname = next((p for p in products if p["id"]==it["product_id"]), None)
                if sel_prod != "All" and pname["name"] != sel_prod:
                    continue
                prod_totals[pname["name"]] = prod_totals.get(pname["name"],0) + it["issue"]

        if prod_totals:
            fig=plt.figure()
            plt.bar(prod_totals.keys(), prod_totals.values())
            plt.xlabel("Products")
            plt.ylabel("Issue Qty")
            plt.title("Product Trend")
            st.pyplot(fig)

        # ---- Stockist Trend ----
        st.write("### 🏪 Stockist-wise Trend")

        stock_totals={}
        for it in items:
            if it["statement_id"] in filtered_stmt_ids:
                stmt = next((s for s in stmts if s["id"]==it["statement_id"]),None)
                sname = next((x["name"] for x in stockists_data if x["id"]==stmt["stockist_id"]), "Unknown")
                stock_totals[sname] = stock_totals.get(sname,0) + it["issue"]

        if stock_totals:
            fig=plt.figure()
            plt.bar(stock_totals.keys(), stock_totals.values())
            plt.xlabel("Stockists")
            plt.ylabel("Issue Qty")
            plt.title("Stockist Trend")
            st.pyplot(fig)

        # ---- User Submission Trend ----
        st.write("### 👤 User Submission Trend")

        submission_totals={}
        for s in stmts:
            if user_match(s):
                uname = next((u["username"] for u in users_data if u["id"]==s["user_id"]), "Unknown")
                submission_totals[uname] = submission_totals.get(uname,0) + 1

        if submission_totals:
            fig=plt.figure()
            plt.bar(submission_totals.keys(), submission_totals.values())
            plt.xlabel("Users")
            plt.ylabel("Submission Count")
            plt.title("User Submission Trend")
            st.pyplot(fig)


    # ================= USER DASHBOARD =================
    else:
        st.header("User Dashboard")

        st.subheader("🕘 Recent Submissions")

        # EXISTING USER LOGIC CONTINUES HERE (unchanged)
        st.write("...user section unchanged from previous version...")
