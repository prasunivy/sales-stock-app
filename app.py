import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTH_ORDER = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ================= SESSION =================
for k in [
    "logged_in","user","nav",
    "statement_id","product_index",
    "edit_user","edit_product","edit_stockist","edit_statement"
]:
    st.session_state.setdefault(k, None)

# ================= HELPERS =================
def safe_select(table, **filters):
    try:
        q = supabase.table(table).select("*")
        for k,v in filters.items():
            q = q.eq(k,v)
        return q.execute().data or []
    except Exception as e:
        st.error(str(e))
        return []

def login(username, password):
    res = safe_select("users",
        username=username.strip(),
        password=password.strip()
    )
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]

        # 🔥 FORCE DEFAULT NAV (FIXES EMPTY ADMIN PAGES)
        if not st.session_state.nav:
            st.session_state.nav = "Users" if res[0]["role"] == "admin" else "My Statements"

        st.rerun()
        return
    st.error("Invalid credentials")

def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

def stmt_key(item, stmts):
    s = next(x for x in stmts if x["id"] == item["statement_id"])
    return (s["year"], MONTH_ORDER.index(s["month"]))

# ================= LOGIN =================
st.title("Ivy Pharmaceuticals — Sales & Stock")

if not st.session_state.logged_in:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True):
        login(u,p)
    st.stop()

user = st.session_state.user
role = user["role"]
uid = user["id"]

# ================= SIDEBAR =================
st.sidebar.title("Menu")

if role == "admin":
    if st.sidebar.button("Users"): st.session_state.nav = "Users"
    if st.sidebar.button("Products"): st.session_state.nav = "Products"
    if st.sidebar.button("Stockists"): st.session_state.nav = "Stockists"
    if st.sidebar.button("Allocate"): st.session_state.nav = "Allocate"
    if st.sidebar.button("Matrix"): st.session_state.nav = "Matrix"
    if st.sidebar.button("Advanced KPI"): st.session_state.nav = "Advanced KPI"

if role == "user":
    if st.sidebar.button("My Statements"): st.session_state.nav = "My Statements"
    if st.sidebar.button("New Statement"): st.session_state.nav = "New Statement"

if st.sidebar.button("Logout"):
    logout()

# Reset edit flags when switching sections
if st.session_state.nav not in ["Users","Products","Stockists"]:
    st.session_state.edit_user = None
    st.session_state.edit_product = None
    st.session_state.edit_stockist = None

# =========================================================
# ================= ADMIN — USERS =========================
# =========================================================
if role=="admin" and st.session_state.nav=="Users":
    st.header("👤 Users")

    uname = st.text_input("Username")
    pwd = st.text_input("Password")
    r = st.selectbox("Role", ["user","admin"])

    if st.button("Add User"):
        supabase.table("users").insert({
            "username": uname,
            "password": pwd,
            "role": r
        }).execute()
        st.rerun()

    for u in safe_select("users"):
        c1,c2,c3,c4 = st.columns([3,2,2,2])
        c1.write(u["username"])
        c2.write(u["role"])
        if c3.button("✏️", key=f"eu{u['id']}"):
            st.session_state.edit_user = u
        if c4.button("🗑", key=f"du{u['id']}"):
            supabase.table("users").delete().eq("id", u["id"]).execute()
            st.rerun()

    if st.session_state.edit_user:
        eu = st.session_state.edit_user
        nr = st.selectbox("Edit Role", ["user","admin"],
                          index=0 if eu["role"]=="user" else 1)
        if st.button("Update User"):
            supabase.table("users").update({"role":nr}).eq("id", eu["id"]).execute()
            st.session_state.edit_user = None
            st.rerun()

# =========================================================
# ================= ADMIN — PRODUCTS ======================
# =========================================================
if role=="admin" and st.session_state.nav=="Products":
    st.header("📦 Products")

    pname = st.text_input("Product Name")
    if st.button("Add Product"):
        supabase.table("products").insert({"name":pname}).execute()
        st.rerun()

    for p in safe_select("products"):
        c1,c2,c3 = st.columns([5,2,2])
        c1.write(p["name"])
        if c2.button("✏️", key=f"ep{p['id']}"):
            st.session_state.edit_product = p
        if c3.button("🗑", key=f"dp{p['id']}"):
            supabase.table("products").delete().eq("id", p["id"]).execute()
            st.rerun()

    if st.session_state.edit_product:
        ep = st.session_state.edit_product
        nn = st.text_input("Edit Product", value=ep["name"])
        if st.button("Update Product"):
            supabase.table("products").update({"name":nn}).eq("id", ep["id"]).execute()
            st.session_state.edit_product = None
            st.rerun()

# =========================================================
# ================= ADMIN — STOCKISTS =====================
# =========================================================
if role=="admin" and st.session_state.nav=="Stockists":
    st.header("🏪 Stockists")

    sname = st.text_input("Stockist Name")
    if st.button("Add Stockist"):
        supabase.table("stockists").insert({"name":sname}).execute()
        st.rerun()

    for s in safe_select("stockists"):
        c1,c2,c3 = st.columns([5,2,2])
        c1.write(s["name"])
        if c2.button("✏️", key=f"es{s['id']}"):
            st.session_state.edit_stockist = s
        if c3.button("🗑", key=f"ds{s['id']}"):
            supabase.table("stockists").delete().eq("id", s["id"]).execute()
            st.rerun()

    if st.session_state.edit_stockist:
        es = st.session_state.edit_stockist
        nn = st.text_input("Edit Stockist", value=es["name"])
        if st.button("Update Stockist"):
            supabase.table("stockists").update({"name":nn}).eq("id", es["id"]).execute()
            st.session_state.edit_stockist = None
            st.rerun()

# =========================================================
# ================= ADMIN — ALLOCATE ======================
# =========================================================
if role=="admin" and st.session_state.nav=="Allocate":
    st.header("🔗 Allocate Stockists")

    users = safe_select("users")
    stockists = safe_select("stockists")

    u = st.selectbox("User", users, format_func=lambda x:x["username"])
    s = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])

    if st.button("Allocate"):
        supabase.table("user_stockist").insert({
            "user_id":u["id"],
            "stockist_id":s["id"]
        }).execute()
        st.success("Allocated")

# =========================================================
# ================= USER — MY STATEMENTS ==================
# =========================================================
if role=="user" and st.session_state.nav=="My Statements":
    st.header("📄 My Statements")

    stmts = safe_select("sales_stock_statements", user_id=uid)
    for s in stmts:
        c1,c2,c3 = st.columns([4,3,2])
        c1.write(f"{s['month']} {s['year']}")
        c2.write(s["status"])
        if c3.button("✏️ Edit", key=f"es{s['id']}"):
            st.session_state.edit_statement = s["id"]
            st.session_state.nav = "Edit Statement"
            st.rerun()

# =========================================================
# ================= USER — EDIT STATEMENT =================
# =========================================================
if role=="user" and st.session_state.nav=="Edit Statement":
    st.header("✏️ Edit Statement")

    stmt_id = st.session_state.edit_statement
    products = safe_select("products")
    items = safe_select("sales_stock_items", statement_id=stmt_id)

    for item in items:
        p = next(x for x in products if x["id"] == item["product_id"])
        with st.form(f"f{item['id']}"):
            st.subheader(p["name"])
            o = st.number_input("Opening", value=item["opening"])
            pu = st.number_input("Purchase", value=item["purchase"])
            i = st.number_input("Issue", value=item["issue"])
            c = st.number_input("Closing", value=item["closing"])
            d = o + pu - i - c
            st.write(f"Difference: {d}")
            if st.form_submit_button("Update", use_container_width=True):
                supabase.table("sales_stock_items").update({
                    "opening":o,"purchase":pu,
                    "issue":i,"closing":c,
                    "difference":d
                }).eq("id", item["id"]).execute()

    if st.button("Re-submit Statement", use_container_width=True):
        supabase.table("sales_stock_statements") \
            .update({"status":"final","locked":True}) \
            .eq("id", stmt_id).execute()
        st.session_state.nav = "My Statements"
        st.session_state.edit_statement = None
        st.rerun()

# =========================================================
# ================= USER — NEW STATEMENT ==================
# =========================================================
if role=="user" and st.session_state.nav=="New Statement":
    st.header("📝 New Statement")

    mappings = safe_select("user_stockist", user_id=uid)
    stockist_ids = [m["stockist_id"] for m in mappings]
    stockists = [s for s in safe_select("stockists") if s["id"] in stockist_ids]

    stck = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
    month = st.selectbox("Month", MONTH_ORDER)
    year = st.number_input("Year", value=datetime.now().year)

    if st.button("Create Statement", use_container_width=True):
        res = supabase.table("sales_stock_statements").insert({
            "user_id":uid,"stockist_id":stck["id"],
            "month":month,"year":int(year),
            "status":"draft","locked":False
        }).execute()
        st.session_state.statement_id = res.data[0]["id"]
        st.session_state.product_index = 0
        st.rerun()

# =========================================================
# ================= PRODUCT ENTRY =========================
# =========================================================
if role=="user" and st.session_state.statement_id:
    products = safe_select("products")
    idx = st.session_state.product_index

    if idx >= len(products):
        supabase.table("sales_stock_statements") \
            .update({"status":"final","locked":True}) \
            .eq("id", st.session_state.statement_id).execute()
        st.success("Statement submitted")
        st.session_state.statement_id = None
        st.stop()

    p = products[idx]
    with st.form("entry"):
        st.subheader(p["name"])
        o = st.number_input("Opening",0)
        pu = st.number_input("Purchase",0)
        i = st.number_input("Issue",0)
        c = st.number_input("Closing",0)
        d = o + pu - i - c
        st.write(f"Difference: {d}")
        if st.form_submit_button("Save & Next", use_container_width=True):
            supabase.table("sales_stock_items").insert({
                "statement_id":st.session_state.statement_id,
                "product_id":p["id"],
                "opening":o,"purchase":pu,
                "issue":i,"closing":c,
                "difference":d
            }).execute()
            st.session_state.product_index += 1
            st.rerun()

# =========================================================
# ================= ADMIN — MATRIX ========================
# =========================================================
if role=="admin" and st.session_state.nav=="Matrix":
    st.header("📊 Stock Matrix")

    stmts = safe_select("sales_stock_statements")
    items = safe_select("sales_stock_items")
    products = safe_select("products")
    stockists = safe_select("stockists")

    year = st.selectbox("Year", sorted({s["year"] for s in stmts}, reverse=True))
    month = st.selectbox("Month", MONTH_ORDER)
    view = st.radio("View", ["Overall","Stockist-wise"], horizontal=True)

    stmt_ids = {s["id"] for s in stmts if s["year"]==year and s["month"]==month}

    rows=[]
    if view=="Overall":
        for p in products:
            pi=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if pi:
                rows.append({
                    "Product":p["name"],
                    "Opening":sum(i["opening"] for i in pi),
                    "Issue":sum(i["issue"] for i in pi),
                    "Closing":sum(i["closing"] for i in pi)
                })
    else:
        for s in stockists:
            s_ids={x["id"] for x in stmts if x["stockist_id"]==s["id"] and x["id"] in stmt_ids}
            for p in products:
                pi=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in s_ids]
                if pi:
                    rows.append({
                        "Stockist":s["name"],
                        "Product":p["name"],
                        "Opening":sum(i["opening"] for i in pi),
                        "Issue":sum(i["issue"] for i in pi),
                        "Closing":sum(i["closing"] for i in pi)
                    })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

# =========================================================
# ================= ADMIN — ADVANCED KPI ==================
# =========================================================
if role=="admin" and st.session_state.nav=="Advanced KPI":
    st.header("📈 Advanced KPI")

    stmts = safe_select("sales_stock_statements")
    items = safe_select("sales_stock_items")
    products = safe_select("products")

    year = st.selectbox("Year", sorted({s["year"] for s in stmts}, reverse=True))
    months = st.multiselect("Months", MONTH_ORDER, default=MONTH_ORDER[-3:])
    stmt_ids = {s["id"] for s in stmts if s["year"]==year and s["month"] in months}

    tabs = st.tabs(["Trend","Idle Stock","High Closing Risk"])

    with tabs[0]:
        rows=[]
        for p in products:
            pi=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if len(pi)>=2:
                pi=sorted(pi, key=lambda x:stmt_key(x,stmts))
                rows.append({
                    "Product":p["name"],
                    "Net Change":pi[-1]["closing"]-pi[0]["closing"]
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with tabs[1]:
        rows=[]
        for p in products:
            pi=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            idle=sum(1 for i in pi if i["issue"]==0 and i["closing"]>0)
            if idle>=2:
                rows.append({"Product":p["name"],"Idle Months":idle})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with tabs[2]:
        rows=[]
        for p in products:
            pi=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if len(pi)>=2:
                avg_issue=sum(i["issue"] for i in pi)/len(pi)
                if avg_issue>0:
                    ratio=round(pi[-1]["closing"]/avg_issue,2)
                    if ratio>1.5:
                        rows.append({"Product":p["name"],"Coverage Ratio":ratio})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.write("---")
st.write("© Ivy Pharmaceuticals")
