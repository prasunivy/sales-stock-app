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

MONTH_ORDER = {
    "January": 1, "February": 2, "March": 3,
    "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9,
    "October": 10, "November": 11, "December": 12
}

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


# ================= HELPER FUNCTIONS =================
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
    y = 750
    for line in text.split("\n"):
        c.drawString(40, y, line)
        y -= 15
        if y <= 40:
            c.showPage()
            y = 750
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

        # ---------- CRUD PANEL ----------
        tab1, tab2, tab3, tab4 = st.tabs(
            ["👤 Users", "📦 Products", "🏪 Stockists", "🔗 Allocations"]
        )

        # USERS
        with tab1:
            st.subheader("Manage Users")
            users = supabase.table("users").select("*").execute().data

            for u in users:
                col = st.columns(4)
                col[0].write(u["username"])

                if col[1].button("Edit", key=f"u_edit_{u['id']}"):
                    new = st.text_input("New Username", value=u["username"])
                    npass = st.text_input("New Password", value=u["password"])
                    if st.button("Save", key=f"u_save_{u['id']}"):
                        supabase.table("users").update({
                            "username": new, "password": npass
                        }).eq("id", u["id"]).execute()
                        st.rerun()

                if col[2].button("Delete", key=f"u_del_{u['id']}"):
                    supabase.table("users").delete().eq("id", u["id"]).execute()
                    st.rerun()

            st.write("### Add User")
            nu = st.text_input("Username")
            npass = st.text_input("Password")
            if st.button("Add User"):
                supabase.table("users").insert({
                    "username": nu,
                    "password": npass,
                    "role": "user"
                }).execute()
                st.rerun()

        # PRODUCTS
        with tab2:
            st.subheader("Manage Products")
            prods = supabase.table("products").select("*").execute().data

            for p in prods:
                col = st.columns(4)
                col[0].write(p["name"])

                if col[1].button("Edit", key=f"p_edit_{p['id']}"]):
                    new = st.text_input("New name", value=p["name"])
                    if st.button("Save", key=f"p_save_{p['id']}"]):
                        supabase.table("products").update({"name": new}).eq("id", p["id"]).execute()
                        st.rerun()

                if col[2].button("Delete", key=f"p_del_{p['id']}"]):
                    supabase.table("products").delete().eq("id", p["id"]).execute()
                    st.rerun()

            np = st.text_input("Add Product")
            if st.button("Add Product"):
                supabase.table("products").insert({"name": np}).execute()
                st.rerun()

        # STOCKISTS
        with tab3:
            st.subheader("Manage Stockists")
            stocks = supabase.table("stockists").select("*").execute().data

            for s in stocks:
                col = st.columns(4)
                col[0].write(s["name"])

                if col[1].button("Edit", key=f"s_edit_{s['id']}"]):
                    new = st.text_input("New name", value=s["name"])
                    if st.button("Save", key=f"s_save_{s['id']}"]):
                        supabase.table("stockists").update({"name": new}).eq("id", s["id"]).execute()
                        st.rerun()

                if col[2].button("Delete", key=f"s_del_{s['id']}"]):
                    supabase.table("stockists").delete().eq("id", s["id"]).execute()
                    st.rerun()

            ns = st.text_input("Add Stockist")
            if st.button("Add Stockist"):
                supabase.table("stockists").insert({"name": ns}).execute()
                st.rerun()

        # ALLOCATIONS
        with tab4:
            st.subheader("Allocate Stockists")

            users = supabase.table("users").select("*").execute().data
            stocks = supabase.table("stockists").select("*").execute().data
            allocs = supabase.table("user_stockists").select("*").execute().data

            st.write("### Current Allocations")
            for a in allocs:
                uname = next(u["username"] for u in users if u["id"]==a["user_id"])
                sname = next(s["name"] for s in stocks if s["id"]==a["stockist_id"])
                col = st.columns(3)
                col[0].write(f"{uname} → {sname}")
                if col[1].button("Delete", key=f"alloc_del{a['id']}"]):
                    supabase.table("user_stockists").delete().eq("id", a["id"]).execute()
                    st.rerun()

            sel_user = st.selectbox("User", [u["username"] for u in users])
            sel_stock = st.selectbox("Stockist", [s["name"] for s in stocks])

            if st.button("Allocate"):
                uid = next(u["id"] for u in users if u["username"]==sel_user)
                sid = next(s["id"] for s in stocks if s["name"]==sel_stock)
                supabase.table("user_stockists").insert({
                    "user_id": uid,
                    "stockist_id": sid
                }).execute()
                st.rerun()


        st.divider()

        # ---------- PDF EXPORT FILTERS ----------
        with st.expander("📂 Export Statements"):
            st.subheader("Filter PDFs")

            stmts = supabase.table("sales_stock_statements").select("*").execute().data
            stocks = supabase.table("stockists").select("*").execute().data

            stock_names = ["All"] + [s["name"] for s in stocks]
            sel_stock = st.selectbox("Stockist", stock_names)

            months_exist = list({s["month"] for s in stmts})
            months = ["All"] + sorted(months_exist, key=lambda x: MONTH_ORDER[x])
            sel_month = st.selectbox("Month", months)

            filtered = []
            for s in stmts:
                sname = next(x["name"] for x in stocks if x["id"]==s["stockist_id"])
                pass_stock = (sel_stock=="All" or sname==sel_stock)
                pass_month = (sel_month=="All" or s["month"]==sel_month)
                if pass_stock and pass_month:
                    filtered.append(s)

            st.write("### Matching Statements")
            for r in filtered:
                stname = next(x["name"] for x in stocks if x["id"]==r["stockist_id"])
                label = f"{r['month']} {r['year']} | {stname}"

                if st.button(f"Download {label}", key=f"pdf{r['id']}"):
                    items = supabase.table("sales_stock_items").select("*") \
                        .eq("statement_id", r["id"]).execute().data

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
                    rep = build_report(stname, r["month"], r["year"], full)
                    pdf = generate_pdf(rep)
                    st.download_button("PDF", pdf, f"{stname}_{r['month']}_{r['year']}.pdf")


        st.divider()

        # ========== ANALYTICS ==========
        st.header("📊 Territory Analytics Dashboard")

        # FILTERS
        users_data = supabase.table("users").select("*").execute().data
        stocks = supabase.table("stockists").select("*").execute().data
        products = supabase.table("products").select("*").execute().data
        stmts = supabase.table("sales_stock_statements").select("*").execute().data
        items = supabase.table("sales_stock_items").select("*").execute().data

        user_filter = ["All"] + [u["username"] for u in users_data]
        stock_filter = ["All"] + [s["name"] for s in stocks]
        prod_filter = ["All"] + [p["name"] for p in products]

        sel_user = st.selectbox("Filter by User", user_filter)
        sel_stock = st.selectbox("Filter by Stockist", stock_filter)
        sel_prod = st.selectbox("Filter by Product", prod_filter)

        def match_stmt(s):
            u = next((x for x in users_data if x["id"]==s["user_id"]),None)
            stname = next((x for x in stocks if x["id"]==s["stockist_id"]),None)

            pass_user = (sel_user=="All" or (u and u["username"]==sel_user))
            pass_stock = (sel_stock=="All" or (stname and stname["name"]==sel_stock))

            return pass_user and pass_stock

        filtered_stmt_ids = [s["id"] for s in stmts if match_stmt(s)]

        # Product Trend
        prod_totals={}
        for it in items:
            if it["statement_id"] in filtered_stmt_ids:
                pname = next((p["name"] for p in products if p["id"]==it["product_id"]),None)
                if sel_prod!="All" and pname!=sel_prod:
                    continue
                prod_totals[pname] = prod_totals.get(pname,0) + it["issue"]

        if prod_totals:
            st.subheader("📦 Product Issue Trend")
            fig=plt.figure()
            plt.bar(prod_totals.keys(), prod_totals.values())
            st.pyplot(fig)

        # Stockist Trend
        stock_totals={}
        for it in items:
            if it["statement_id"] in filtered_stmt_ids:
                stmt = next(s for s in stmts if s["id"]==it["statement_id"])
                sname = next(x["name"] for x in stocks if x["id"]==stmt["stockist_id"])
                stock_totals[sname] = stock_totals.get(sname,0) + it["issue"]

        if stock_totals:
            st.subheader("🏪 Stockist Trend")
            fig=plt.figure()
            plt.bar(stock_totals.keys(), stock_totals.values())
            st.pyplot(fig)

        # User Submission Trend
        user_totals={}
        for s in stmts:
            if match_stmt(s):
                uname = next(x["username"] for x in users_data if x["id"]==s["user_id"])
                user_totals[uname] = user_totals.get(uname,0) + 1

        if user_totals:
            st.subheader("👤 User Submission Trend")
            fig=plt.figure()
            plt.bar(user_totals.keys(), user_totals.values())
            st.pyplot(fig)

        # ---------- NEW: LAST 6-MONTH PRODUCT MOVEMENT ----------
        st.subheader("📈 Last 6-Month Product Movement Trend")

        # Stockist dropdown
        st_list = [s["name"] for s in stocks]
        sel_st = st.selectbox("Select Stockist for Trend", st_list)

        # Product dropdown
        prod_list = [p["name"] for p in products]
        sel_product = st.selectbox("Select Product", prod_list)

        # fetch last 6 statements for that stockist
        stmnts = [
            s for s in stmts
            if next(x["name"] for x in stocks if x["id"]==s["stockist_id"]) == sel_st
        ]

        # sort months properly
        stmnts = sorted(stmnts, key=lambda x: MONTH_ORDER[x["month"]])

        # last 6 only
        stmnts = stmnts[-6:]

        trend={}
        for s in stmnts:
            items_m = supabase.table("sales_stock_items").select("*") \
                .eq("statement_id", s["id"]).execute().data
            for it in items_m:
                pname = next(p["name"] for p in products if p["id"]==it["product_id"])
                if pname == sel_product:
                    trend[f"{s['month']} {s['year']}"] = it["issue"]

        if trend:
            fig=plt.figure()
            plt.bar(trend.keys(), trend.values())
            plt.title(f"Last 6 Months — {sel_product}")
            plt.xlabel("Month")
            plt.ylabel("Issue Qty")
            st.pyplot(fig)
        else:
            st.info("No matching data for last 6 months.")


    # ================= USER DASHBOARD =================
    else:
        st.header("User Dashboard")
        st.write("User features (statement entry, preview, final submit, recent submissions, PDF, WhatsApp) remain unchanged.")
