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
    "April","May","June","July","August","September",
    "October","November","December","January","February","March"
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
    except:
        return []

def login(u,p):
    res = safe_select("users", username=u.strip(), password=p.strip())
    if res:
        st.session_state.logged_in = True
        st.session_state.user = res[0]
        if not st.session_state.nav:
            st.session_state.nav = "Users" if res[0]["role"]=="admin" else "My Statements"
        st.rerun()
    st.error("Invalid credentials")

def logout():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

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
    stockists = safe_select("stockists")
    smap = {s["id"]: s["name"] for s in stockists}

    for s in stmts:
        c1,c2,c3,c4 = st.columns([3,3,3,2])
        c1.write(f"{s['month']} {s['year']}")
        c2.write(smap.get(s["stockist_id"], "—"))
        c3.write(s["status"])
        if c4.button("✏️ Edit", key=f"es{s['id']}"):
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
# ================= PRODUCT ENTRY (SORTED A–Z) ============
# =========================================================
if role=="user" and st.session_state.statement_id:
    # 🔥 SORT PRODUCTS IN ASCENDING ORDER
    products = sorted(
        safe_select("products"),
        key=lambda x: (x.get("name") or "").lower()
    )

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
    st.header("📊 Matrix Dashboard")

    stmts = safe_select("sales_stock_statements")
    items = safe_select("sales_stock_items")
    products = safe_select("products")
    stockists = safe_select("stockists")
    users = safe_select("users")

    tab1, tab2 = st.tabs([
        "📦 Stock Matrix",
        "📈 Product Issue Matrix (User-wise)"
    ])

    # ---------- TAB 1 ----------
    with tab1:
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
                        "Purchase":sum(i["purchase"] for i in pi),
                        "Issue":sum(i["issue"] for i in pi),
                        "Closing":sum(i["closing"] for i in pi),
                        "Difference":sum(i["difference"] for i in pi)
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
                            "Purchase":sum(i["purchase"] for i in pi),
                            "Issue":sum(i["issue"] for i in pi),
                            "Closing":sum(i["closing"] for i in pi),
                            "Difference":sum(i["difference"] for i in pi)
                        })

        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # ---------- TAB 2 ----------
    with tab2:
        sel_user = st.selectbox(
            "Select User",
            [u for u in users if u["role"]=="user"],
            format_func=lambda x:x["username"]
        )

        user_stmt_ids = {s["id"] for s in stmts if s["user_id"]==sel_user["id"]}

        rows=[]
        for p in products:
            row={"Product":p["name"]}
            total=0
            for m in MONTH_ORDER:
                qty=sum(
                    i["issue"] for i in items
                    if i["product_id"]==p["id"]
                    and i["statement_id"] in user_stmt_ids
                    and any(s["id"]==i["statement_id"] and s["month"]==m for s in stmts)
                )
                row[m]=qty
                total+=qty
            if total>0:
                row["Total"]=total
                rows.append(row)

        df=pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇️ Download CSV",
                           df.to_csv(index=False),
                           f"product_issue_matrix_{sel_user['username']}.csv")

st.write("---")
st.write("© Ivy Pharmaceuticals")
