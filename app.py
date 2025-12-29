import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# ================= CONFIG =================
st.set_page_config("Ivy Pharmaceuticals — Sales & Stock", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MONTH_ORDER = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]

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
    except:
        return []

def login(u,p):
    res = safe_select("users", username=u.strip(), password=p.strip())
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        st.session_state.nav = "Users" if res[0]["role"]=="admin" else "My Statements"
        st.rerun()
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

if role=="admin":
    for m in ["Users","Products","Stockists","Allocate","Matrix","Advanced KPI"]:
        if st.sidebar.button(m):
            st.session_state.nav = m

if role=="user":
    for m in ["My Statements","New Statement"]:
        if st.sidebar.button(m):
            st.session_state.nav = m

if st.sidebar.button("Logout"):
    logout()

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
            opening = st.number_input("Opening", value=item["opening"])
            purchase = st.number_input("Purchase", value=item["purchase"])
            issue = st.number_input("Issue", value=item["issue"])
            closing = st.number_input("Closing", value=item["closing"])
            diff = opening + purchase - issue - closing
            st.write(f"Difference: {diff}")
            if st.form_submit_button("Update", use_container_width=True):
                supabase.table("sales_stock_items").update({
                    "opening":opening,"purchase":purchase,
                    "issue":issue,"closing":closing,
                    "difference":diff
                }).eq("id", item["id"]).execute()
                st.success("Updated")

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

    stockist = st.selectbox("Stockist", stockists, format_func=lambda x:x["name"])
    month = st.selectbox("Month", MONTH_ORDER)
    year = st.number_input("Year", value=datetime.now().year)

    if st.button("Create Statement", use_container_width=True):
        res = supabase.table("sales_stock_statements").insert({
            "user_id":uid,"stockist_id":stockist["id"],
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
        opening = st.number_input("Opening",0)
        purchase = st.number_input("Purchase",0)
        issue = st.number_input("Issue",0)
        closing = st.number_input("Closing",0)
        diff = opening + purchase - issue - closing
        st.write(f"Difference: {diff}")
        if st.form_submit_button("Save & Next", use_container_width=True):
            supabase.table("sales_stock_items").insert({
                "statement_id":st.session_state.statement_id,
                "product_id":p["id"],
                "opening":opening,"purchase":purchase,
                "issue":issue,"closing":closing,
                "difference":diff
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
            p_items=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if p_items:
                rows.append({
                    "Product":p["name"],
                    "Opening":sum(i["opening"] for i in p_items),
                    "Purchase":sum(i["purchase"] for i in p_items),
                    "Issue":sum(i["issue"] for i in p_items),
                    "Closing":sum(i["closing"] for i in p_items)
                })
    else:
        for s in stockists:
            s_stmt_ids={x["id"] for x in stmts if x["stockist_id"]==s["id"] and x["id"] in stmt_ids}
            for p in products:
                p_items=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in s_stmt_ids]
                if p_items:
                    rows.append({
                        "Stockist":s["name"],
                        "Product":p["name"],
                        "Opening":sum(i["opening"] for i in p_items),
                        "Issue":sum(i["issue"] for i in p_items),
                        "Closing":sum(i["closing"] for i in p_items)
                    })

    df=pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    st.download_button("⬇️ CSV", df.to_csv(index=False), "matrix.csv")

# =========================================================
# ================= ADMIN — ADVANCED KPI ==================
# =========================================================
if role=="admin" and st.session_state.nav=="Advanced KPI":
    st.header("📈 Advanced KPI")

    stmts=safe_select("sales_stock_statements")
    items=safe_select("sales_stock_items")
    products=safe_select("products")

    year=st.selectbox("Year", sorted({s["year"] for s in stmts}, reverse=True))
    months=st.multiselect("Months", MONTH_ORDER, default=MONTH_ORDER[-3:])
    stmt_ids={s["id"] for s in stmts if s["year"]==year and s["month"] in months}

    tabs=st.tabs(["Trend","Idle Stock","High Closing Risk"])

    with tabs[0]:
        rows=[]
        for p in products:
            p_items=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if len(p_items)>=2:
                p_items=sorted(p_items, key=lambda x:stmt_key(x,stmts))
                rows.append({
                    "Product":p["name"],
                    "Net Change":p_items[-1]["closing"]-p_items[0]["closing"]
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with tabs[1]:
        rows=[]
        for p in products:
            p_items=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            idle=sum(1 for i in p_items if i["issue"]==0 and i["closing"]>0)
            if idle>=2:
                rows.append({"Product":p["name"],"Idle Months":idle})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with tabs[2]:
        rows=[]
        for p in products:
            p_items=[i for i in items if i["product_id"]==p["id"] and i["statement_id"] in stmt_ids]
            if len(p_items)>=2:
                avg_issue=sum(i["issue"] for i in p_items)/len(p_items)
                if avg_issue>0:
                    ratio=round(p_items[-1]["closing"]/avg_issue,2)
                    if ratio>1.5:
                        rows.append({"Product":p["name"],"Coverage":ratio})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

st.write("---")
st.write("© Ivy Pharmaceuticals")
