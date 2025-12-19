import streamlit as st
from supabase import create_client
from datetime import date
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTH_ORDER = {
    "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
    "July":7,"August":8,"September":9,"October":10,"November":11,"December":12
}

# ================= SESSION DEFAULTS =================
session_defaults = {
    "logged_in": False,
    "user": None,
    "nav": "home",
    "statement_id": None,
    "selected_stockist": None,
    "from_date": None,
    "to_date": None,
    "year": None,
    "month": None,
    "product_index": 0,
    "products_cache": [],
    "product_data": {},
}

for k,v in session_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ================= HELPERS =================
def login(username, password):
    res = supabase.table("users").select("*")\
        .eq("username", username.strip())\
        .eq("password", password.strip()).execute()

    if res.data:
        st.session_state.logged_in = True
        st.session_state.user = res.data[0]
        st.rerun()
    else:
        st.error("Invalid credentials")


def logout():
    st.session_state.clear()
    for k,v in session_defaults.items():
        st.session_state[k] = v
    st.rerun()


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


# ================= UI TITLE =================
st.title("Ivy Pharmaceuticals — Sales & Stock App")

# ================= LOGIN =================
if not st.session_state.logged_in:
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        login(username, password)
    st.stop()


# ================= SIDEBAR NAVIGATION =================
role = st.session_state.user["role"]

st.sidebar.title("Navigation")

if st.sidebar.button("🏠 Home"):
    st.session_state.nav = "home"

if role == "admin":

    if st.sidebar.button("👤 Manage Users"):
        st.session_state.nav = "users"

    if st.sidebar.button("📦 Manage Products"):
        st.session_state.nav = "products"

    if st.sidebar.button("🏪 Manage Stockists"):
        st.session_state.nav = "stockists"

    if st.sidebar.button("🔗 Allocate Stockists"):
        st.session_state.nav = "allocate"

    if st.sidebar.button("📂 Export Statements"):
        st.session_state.nav = "export"

    if st.sidebar.button("📊 Analytics Dashboard"):
        st.session_state.nav = "analytics"

    if st.sidebar.button("📈 Product Trend"):
        st.session_state.nav = "trend"

    if st.sidebar.button("🤖 AI Suggestions"):
        st.session_state.nav = "ai"

    if st.sidebar.button("📋 Summary Matrices"):
        st.session_state.nav = "matrices"

else:

    if st.sidebar.button("➕ Create Statement"):
        st.session_state.nav = "create"

    if st.sidebar.button("🕘 Recent Submissions"):
        st.session_state.nav = "recent"

    if st.sidebar.button("📁 My Reports"):
        st.session_state.nav = "reports"

    if st.sidebar.button("🤖 AI Suggestions"):
        st.session_state.nav = "ai"

if st.sidebar.button("🚪 Logout"):
    logout()


# ================= ADMIN — USERS =================
if role == "admin" and st.session_state.nav == "users":
    st.header("👤 Manage Users")

    users = supabase.table("users").select("*").execute().data

    # add user
    with st.expander("➕ Add User"):
        uname = st.text_input("Username")
        upass = st.text_input("Password", type="password")
        urole = st.selectbox("Role", ["user", "admin"])
        if st.button("Add User"):
            supabase.table("users").insert({
                "username": uname,
                "password": upass,
                "role": urole
            }).execute()
            st.success("User added!")
            st.rerun()

    # edit / delete
    with st.expander("✏️ Edit / Delete Users"):
        for u in users:
            col = st.columns(4)
            col[0].write(u["username"])
            if col[1].button("Edit", key=f"edit_user{u['id']}"):
                st.session_state.edit_user = u["id"]
            if col[2].button("Delete", key=f"del_user{u['id']}"):

                # keep statements but remove user link
                supabase.table("sales_stock_statements")\
                        .update({"user_id": None}).eq("user_id", u["id"]).execute()

                # remove allocations
                supabase.table("user_stockists")\
                        .delete().eq("user_id", u["id"]).execute()

                supabase.table("users").delete().eq("id", u["id"]).execute()

                st.success("User deleted — statements retained.")
                st.rerun()

        if "edit_user" in st.session_state:
            uid = st.session_state.edit_user
            user = next(u for u in users if u["id"] == uid)

            newname = st.text_input("New Username", user["username"])
            newpass = st.text_input("New Password", user["password"])
            newrole = st.selectbox("Role", ["user","admin"], index=0 if user["role"]=="user" else 1)

            if st.button("Update User"):
                supabase.table("users").update({
                    "username": newname,
                    "password": newpass,
                    "role": newrole
                }).eq("id", uid).execute()

                st.success("Updated")
                del st.session_state.edit_user
                st.rerun()


# ================= ADMIN — PRODUCTS =================
if role == "admin" and st.session_state.nav == "products":
    st.header("📦 Manage Products")

    products = supabase.table("products").select("*").execute().data

    with st.expander("➕ Add Product"):
        pname = st.text_input("Product Name")
        peak = st.multiselect("Peak Months", MONTH_ORDER.keys())
        high = st.multiselect("High Months", MONTH_ORDER.keys())
        low = st.multiselect("Low Months", MONTH_ORDER.keys())
        lowest = st.multiselect("Lowest Months", MONTH_ORDER.keys())

        if st.button("Add Product"):
            supabase.table("products").insert({
                "name": pname,
                "season_peak_months": peak,
                "season_high_months": high,
                "season_low_months": low,
                "season_lowest_months": lowest
            }).execute()
            st.success("Product added!")
            st.rerun()

    with st.expander("✏️ Edit / Delete Products"):
        for p in products:
            col = st.columns(5)
            col[0].write(p["name"])
            if col[1].button("Edit", key=f"edit_prod{p['id']}"):
                st.session_state.edit_product = p["id"]
            if col[2].button("Delete", key=f"del_prod{p['id']}"):
                supabase.table("products").delete().eq("id", p["id"]).execute()
                st.success("Deleted")
                st.rerun()

        if "edit_product" in st.session_state:
            pid = st.session_state.edit_product
            prod = next(p for p in products if p["id"] == pid)

            newname = st.text_input("Product Name", prod["name"])

            peak = st.multiselect("Peak Months", MONTH_ORDER.keys(), prod["season_peak_months"] or [])
            high = st.multiselect("High Months", MONTH_ORDER.keys(), prod["season_high_months"] or [])
            low = st.multiselect("Low Months", MONTH_ORDER.keys(), prod["season_low_months"] or [])
            lowest = st.multiselect("Lowest Months", MONTH_ORDER.keys(), prod["season_lowest_months"] or [])

            if st.button("Update Product"):
                supabase.table("products").update({
                    "name": newname,
                    "season_peak_months": peak,
                    "season_high_months": high,
                    "season_low_months": low,
                    "season_lowest_months": lowest
                }).eq("id", pid).execute()

                st.success("Updated")
                del st.session_state.edit_product
                st.rerun()


# ================= ADMIN — STOCKISTS =================
if role == "admin" and st.session_state.nav == "stockists":
    st.header("🏪 Manage Stockists")

    stockists = supabase.table("stockists").select("*").execute().data

    with st.expander("➕ Add Stockist"):
        sname = st.text_input("Stockist Name")
        if st.button("Add Stockist"):
            supabase.table("stockists").insert({"name": sname}).execute()
            st.success("Stockist added!")
            st.rerun()

    with st.expander("✏️ Edit / Delete Stockists"):
        for s in stockists:
            col = st.columns(3)
            col[0].write(s["name"])
            if col[1].button("Edit", key=f"edit_stock{s['id']}"):
                st.session_state.edit_stock = s["id"]
            if col[2].button("Delete", key=f"del_stock{s['id']}"):

                supabase.table("sales_stock_statements")\
                    .update({"stockist_id": None}).eq("stockist_id", s["id"]).execute()

                supabase.table("user_stockists")\
                    .delete().eq("stockist_id", s["id"]).execute()

                supabase.table("stockists").delete().eq("id", s["id"]).execute()

                st.success("Stockist deleted")
                st.rerun()


    if "edit_stock" in st.session_state:
        sid = st.session_state.edit_stock
        stock = next(s for s in stockists if s["id"] == sid)
        newname = st.text_input("Stockist Name", stock["name"])

        if st.button("Update Stockist"):
            supabase.table("stockists").update({"name": newname}).eq("id", sid).execute()
            st.success("Updated")
            del st.session_state.edit_stock
            st.rerun()


# ================= ADMIN — ALLOCATE STOCKISTS =================
if role == "admin" and st.session_state.nav == "allocate":
    st.header("🔗 Allocate Stockists")

    users = supabase.table("users").select("*").execute().data
    stockists = supabase.table("stockists").select("*").execute().data
    allocs = supabase.table("user_stockists").select("*").execute().data

    user_map = {u["username"]: u for u in users}
    stock_map = {s["name"]: s for s in stockists}

    with st.expander("➕ New Allocation"):
        uname = st.selectbox("User", user_map.keys())
        sname = st.selectbox("Stockist", stock_map.keys())

        if st.button("Allocate"):
            supabase.table("user_stockists").insert({
                "user_id": user_map[uname]["id"],
                "stockist_id": stock_map[sname]["id"]
            }).execute()
            st.success("Allocated")
            st.rerun()

    with st.expander("✏️ Delete Allocation"):
        for a in allocs:
            u = next(u for u in users if u["id"] == a["user_id"])
            s = next(s for s in stockists if s["id"] == a["stockist_id"])
            col = st.columns(3)
            col[0].write(u["username"])
            col[1].write(s["name"])
            if col[2].button("Delete", key=f"del_alloc{a['id']}"):
                supabase.table("user_stockists").delete().eq("id", a["id"]).execute()
                st.success("Deleted")
                st.rerun()
# ================= USER SCREENS =================

# HOME
if role != "admin" and st.session_state.nav == "home":
    st.header(f"Welcome {st.session_state.user['username']}")
    st.write("Use the sidebar to begin.")


# ========== CREATE STATEMENT STEP 1 ==========
if role != "admin" and st.session_state.nav == "create":
    st.header("➕ Create Sales & Stock Statement — Step 1")

    allocs = supabase.table("user_stockists").select("*")\
        .eq("user_id", st.session_state.user["id"]).execute().data

    if not allocs:
        st.warning("No stockists allocated to you.")
        st.stop()

    stock_ids = [a["stockist_id"] for a in allocs]
    stockists = supabase.table("stockists").select("*").execute().data
    stock = [s for s in stockists if s["id"] in stock_ids]

    stockmap = {s["name"]: s["id"] for s in stock}

    sname = st.selectbox("Select Stockist", stockmap.keys())
    year = st.selectbox("Year", [date.today().year, date.today().year - 1])
    month = st.selectbox("Month", list(MONTH_ORDER.keys()))
    fdate = st.date_input("From Date")
    tdate = st.date_input("To Date")

    if st.button("Temporary Submit"):
        stmt = supabase.table("sales_stock_statements").insert({
            "user_id": st.session_state.user["id"],
            "stockist_id": stockmap[sname],
            "year": str(year),   # store as string for safety
            "month": month,
            "from_date": fdate.isoformat(),
            "to_date": tdate.isoformat()
        }).execute()

        st.session_state.statement_id = stmt.data[0]["id"]
        st.session_state.year = str(year)
        st.session_state.month = month
        st.session_state.selected_stockist = stockmap[sname]

        st.session_state.product_index = 0
        st.session_state.products_cache = supabase.table("products").select("*").execute().data
        st.session_state.product_data = {}
        st.session_state.nav = "entry"
        st.rerun()


# ========== PRODUCT ENTRY ==========
if role != "admin" and st.session_state.nav == "entry":
    st.header("Enter Product Details")

    products = st.session_state.products_cache
    idx = st.session_state.product_index

    if idx >= len(products):
        st.session_state.nav = "preview"
        st.rerun()

    prod = products[idx]
    st.subheader(prod["name"])

    prev = supabase.table("sales_stock_items").select("*")\
        .eq("product_id", prod["id"])\
        .eq("statement_id", st.session_state.statement_id).execute().data

    old = prev[0] if prev else None

    past_items = supabase.table("sales_stock_items").select("*")\
        .eq("product_id", prod["id"]).execute().data

    last_close = past_items[-1]["closing"] if past_items else 0

    st.info(f"Last Month Closing: {last_close}")

    opening = st.number_input("Opening", value= last_close if not old else old["opening"])
    purchase = st.number_input("Purchase", value=0 if not old else old["purchase"])
    issue = st.number_input("Issue", value=0 if not old else old["issue"])
    closing = st.number_input("Closing", value=0 if not old else old["closing"])

    diff = opening + purchase - issue - closing
    st.write(f"Difference: {diff}")

    st.session_state.product_data[prod["id"]] = {
        "opening": opening,
        "purchase": purchase,
        "issue": issue,
        "closing": closing,
        "difference": diff
    }

    col = st.columns(2)
    if col[0].button("Next Product"):
        st.session_state.product_index += 1
        st.rerun()

    if idx > 0 and col[1].button("Previous Product"):
        st.session_state.product_index -= 1
        st.rerun()


# ========== PREVIEW BEFORE FINAL SUBMIT ==========
if role != "admin" and st.session_state.nav == "preview":
    st.header("Preview Before Final Submit")

    data = st.session_state.product_data
    rows = []
    products = st.session_state.products_cache

    for p in products:
        if p["id"] in data:
            rows.append({"Product": p["name"], **data[p["id"]]})

    df = pd.DataFrame(rows)
    st.dataframe(df)

    if st.button("Final Submit"):
        for pid, d in data.items():
            supabase.table("sales_stock_items").insert({
                "statement_id": st.session_state.statement_id,
                "product_id": pid,
                "opening": d["opening"],
                "purchase": d["purchase"],
                "issue": d["issue"],
                "closing": d["closing"],
                "difference": d["difference"]
            }).execute()

        st.success("Statement Submitted!")
        st.session_state.nav = "recent"
        st.rerun()


# ========== RECENT SUBMISSIONS ==========
if role != "admin" and st.session_state.nav == "recent":
    st.header("Recent Submissions")

    stmts = supabase.table("sales_stock_statements")\
        .select("*")\
        .eq("user_id", st.session_state.user["id"]).execute().data

    for s in stmts[::-1]:
        col = st.columns(2)
        col[0].write(f"{s['month']} {s['year']}")
        if col[1].button("View", key=f"v{s['id']}"):
            st.session_state.view_stmt = s["id"]
            st.session_state.nav = "reports"
            st.rerun()


# ========== REPORTS ==========
if role != "admin" and st.session_state.nav == "reports":
    st.header("Reports")

    if "view_stmt" not in st.session_state:
        st.info("Select a submission from Recent.")
        st.stop()

    sid = st.session_state.view_stmt

    items = supabase.table("sales_stock_items").select("*")\
        .eq("statement_id", sid).execute().data

    if not items:
        st.warning("No data.")
        st.stop()

    df = pd.DataFrame(items)
    st.dataframe(df)

    if st.button("Download PDF Report"):
        txt = df.to_string()
        pdf = generate_pdf(txt)
        st.download_button("Download PDF", data=pdf, file_name="report.pdf")


# ================= ADMIN — EXPORT ==========

if role == "admin" and st.session_state.nav == "export":
    st.header("📂 Export Statements")

    items = supabase.table("sales_stock_items").select("*").execute().data

    if st.button("Download All to CSV"):
        df = pd.DataFrame(items)
        st.download_button("Download CSV", df.to_csv(index=False), "all_items.csv")


# ================= ADMIN — ANALYTICS ==========
if role == "admin" and st.session_state.nav == "analytics":
    st.header("📊 Territory Analytics")

    items = supabase.table("sales_stock_items").select("*").execute().data
    prods = supabase.table("products").select("*").execute().data

    totals = {}
    for it in items:
        totals[it["product_id"]] = totals.get(it["product_id"], 0) + it["issue"]

    names = [p["name"] for p in prods]
    vals = [totals.get(p["id"], 0) for p in prods]

    fig, ax = plt.subplots()
    ax.bar(names, vals)
    st.pyplot(fig)


# ================= ADMIN — PRODUCT TREND ==========
if role == "admin" and st.session_state.nav == "trend":
    st.header("📈 Product Trend")

    prods = supabase.table("products").select("*").execute().data
    pname = st.selectbox("Select Product", [p["name"] for p in prods])

    prod = next(p for p in prods if p["name"] == pname)

    items = supabase.table("sales_stock_items").select("*")\
        .eq("product_id", prod["id"]).execute().data

    monthly = {}

    for it in items:
        stmt = supabase.table("sales_stock_statements").select("*")\
            .eq("id", it["statement_id"]).execute().data[0]
        month = stmt["month"]
        monthly[month] = monthly.get(month, 0) + it["issue"]

    fig, ax = plt.subplots()
    ax.plot(list(monthly.keys()), list(monthly.values()))
    st.pyplot(fig)


# ================= AI SUGGESTIONS ==========
if st.session_state.nav == "ai":
    st.header("🤖 AI Suggestions")

    stockists = supabase.table("stockists").select("*").execute().data
    sname = st.selectbox("Select Stockist", [s["name"] for s in stockists])
    month = st.selectbox("Select Month", list(MONTH_ORDER.keys()))

    sid = next(s["id"] for s in stockists if s["name"] == sname)

    prods = supabase.table("products").select("*").execute().data
    items = supabase.table("sales_stock_items").select("*").execute().data
    stmts = supabase.table("sales_stock_statements").select("*")\
        .eq("stockist_id", sid).execute().data

    for p in prods:
        hist = [it["issue"] for it in items if it["product_id"] == p["id"]]
        avg = sum(hist[-6:]) / min(6, len(hist)) if hist else 0

        if p["season_peak_months"] and month in p["season_peak_months"]:
            f = 1.8
        elif p["season_high_months"] and month in p["season_high_months"]:
            f = 1.5
        elif p["season_low_months"] and month in p["season_low_months"]:
            f = 0.7
        elif p["season_lowest_months"] and month in p["season_lowest_months"]:
            f = 0.4
        else:
            f = 1.0

        predicted = avg * f

        closing = 0
        if stmts:
            last_stmt = stmts[-1]["id"]
            last_item = [
                it for it in items if it["statement_id"] == last_stmt and it["product_id"] == p["id"]
            ]
            if last_item:
                closing = last_item[0]["closing"]

        order = predicted * 1.5 - closing

        st.subheader(p["name"])
        st.write(f"Predicted Issue: {int(predicted)}")
        st.write(f"Recommended Order: {int(order)}")


# ================= SUMMARY MATRICES ==========
if role == "admin" and st.session_state.nav == "matrices":
    st.header("📋 Summary Matrices")

    # ===== Matrix 1 =====
    st.subheader("Matrix 1 — Month & Year → Product Summary")

    year = st.selectbox("Select Year", [str(date.today().year), str(date.today().year-1)], key="m1y")
    month = st.selectbox("Select Month", list(MONTH_ORDER.keys()), key="m1m")

    stmts = supabase.table("sales_stock_statements")\
        .select("*").execute().data

    stmts = [s for s in stmts if str(s["year"]) == str(year) and s["month"] == month]

    stmt_ids = [s["id"] for s in stmts]

    items = supabase.table("sales_stock_items").select("*").execute().data
    prods = supabase.table("products").select("*").execute().data

    rows = []
    for p in prods:
        f = [it for it in items if it["statement_id"] in stmt_ids and it["product_id"] == p["id"]]
        if f:
            op = sum(it["opening"] for it in f)
            pu = sum(it["purchase"] for it in f)
            is_ = sum(it["issue"] for it in f)
            cl = sum(it["closing"] for it in f)
            diff = sum(it.get("difference", 0) for it in f)
            order = is_ * 1.5 - cl
            rows.append([p["name"], op, pu, is_, cl, diff, order])

    df = pd.DataFrame(rows, columns=["Product","Opening","Purchase","Issue","Closing","Difference","Order"])
    st.dataframe(df)


    # ===== Matrix 2 =====
    st.subheader("Matrix 2 — Product & Year → Monthly Summary")

    pname = st.selectbox("Select Product", [p["name"] for p in prods], key="m2p")
    year2 = st.selectbox("Select Year", [str(date.today().year), str(date.today().year-1)], key="m2y")

    prod = next(p for p in prods if p["name"] == pname)

    # 12 fixed month columns
    mcols = list(MONTH_ORDER.keys())

    mat = {
        "Opening": [0]*12,
        "Purchase": [0]*12,
        "Issue": [0]*12,
        "Closing": [0]*12,
        "Difference": [0]*12,
        "Order": [0]*12
    }

    # safe fetch of all statements
    stmts2 = supabase.table("sales_stock_statements").select("*").execute().data
    stmts2 = [s for s in stmts2 if str(s["year"]) == str(year2)]

    # fetch all items (we filter afterward)
    items2 = supabase.table("sales_stock_items").select("*").execute().data

    for i, m in enumerate(mcols):
        sids = [s["id"] for s in stmts2 if s["month"] == m]
        f = [it for it in items2 if it["product_id"] == prod["id"] and it["statement_id"] in sids]

        if f:
            mat["Opening"][i] = sum(it["opening"] for it in f)
            mat["Purchase"][i] = sum(it["purchase"] for it in f)
            mat["Issue"][i] = sum(it["issue"] for it in f)
            mat["Closing"][i] = sum(it["closing"] for it in f)
            mat["Difference"][i] = sum(it.get("difference", 0) for it in f)
            mat["Order"][i] = mat["Issue"][i] * 1.5 - mat["Closing"][i]

    df2 = pd.DataFrame(mat, index=["Opening","Purchase","Issue","Closing","Difference","Order"], columns=mcols)
    st.dataframe(df2)


# ================= FOOTER =================
st.write("---")
st.write("© Ivy Pharmaceuticals 2025 — All Rights Reserved.")
