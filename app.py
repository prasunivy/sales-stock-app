import streamlit as st
from supabase import create_client
from datetime import date
import urllib.parse
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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
            f"I:{d['issue']} C:{d['closing']} D:{d['diff']} "
            f"| Order:{order_qty}"
        )
        if remarks:
            lines.append(" • " + ", ".join(remarks))

    return "\n".join(lines)


# PDF Generator
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
        login(u,p)


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
            summary=[]
            for r in data:
                u = supabase.table("users").select("username").eq("id", r["user_id"]).execute()
                s = supabase.table("stockists").select("name").eq("id", r["stockist_id"]).execute()
                summary.append({
                    "statement_id": r.get("id"),
                    "username": u.data[0]["username"] if u.data else "Unknown",
                    "stockist": s.data[0]["name"] if s.data else "Unknown",
                    "from_date": r.get("from_date",""),
                    "to_date": r.get("to_date",""),
                    "month": r.get("month",""),
                    "year": r.get("year","")
                })
            df = pd.DataFrame(summary)
            st.download_button("Download Summary CSV", df.to_csv(index=False), "summary.csv")

        # Detailed CSV
        if st.button("Download Item Details CSV"):
            items = supabase.table("sales_stock_items").select("*").execute().data
            detailed=[]
            for it in items:
                stmt = supabase.table("sales_stock_statements").select("*").eq("id", it["statement_id"]).execute()
                rec = stmt.data[0] if stmt.data else {}
                u = supabase.table("users").select("username").eq("id", rec.get("user_id")).execute()
                s = supabase.table("stockists").select("name").eq("id", rec.get("stockist_id")).execute()
                p = supabase.table("products").select("name").eq("id", it["product_id"]).execute()
                detailed.append({
                    "statement_id": it.get("statement_id"),
                    "username": u.data[0]["username"] if u.data else "Unknown",
                    "stockist": s.data[0]["name"] if s.data else "Unknown",
                    "from_date": rec.get("from_date",""),
                    "to_date": rec.get("to_date",""),
                    "month": rec.get("month",""),
                    "year": rec.get("year",""),
                    "product": p.data[0]["name"] if p.data else "Unknown",
                    "opening": it.get("opening"),
                    "purchase": it.get("purchase"),
                    "issue": it.get("issue"),
                    "closing": it.get("closing"),
                    "difference": it.get("diff_closing"),
                })
            df = pd.DataFrame(detailed)
            st.download_button("Download Detailed CSV", df.to_csv(index=False), "items.csv")

        # Admin PDF
        st.subheader("📄 Export Statements as PDF")
        data = supabase.table("sales_stock_statements").select("*").execute().data
        for r in data:
            sname = supabase.table("stockists").select("name").eq("id", r["stockist_id"]).execute().data
            stock = sname[0]["name"] if sname else "Unknown"
            label = f"{r['month']} {r['year']} | {stock}"
            if st.button(f"PDF: {label}", key=f"adm_pdf{r['id']}"):
                items = supabase.table("sales_stock_items").select("*").eq("statement_id", r["id"]).execute().data
                full=[]
                for it in items:
                    pname = supabase.table("products").select("name").eq("id",it["product_id"]).execute().data
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


    # ================= USER DASHBOARD =================
    else:
        st.header("User Dashboard")

        # Recent Submissions
        st.subheader("🕘 Recent Submissions")
        uid=user["id"]
        rec = supabase.table("sales_stock_statements").select("*").eq("user_id",uid).order("from_date",desc=True).execute().data

        for r in rec:
            s = supabase.table("stockists").select("name").eq("id", r["stockist_id"]).execute().data
            stock_name = s[0]["name"] if s else "Unknown"
            label = f"{r['month']} {r['year']} | {stock_name}"

            if st.button(f"View: {label}", key=f"view{r['id']}"):
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

                rep = build_report(stock_name, r["month"], r["year"], full)
                st.session_state.recent_view_report = rep
                st.session_state.recent_view_title = label
                st.rerun()

        if st.session_state.recent_view_report:
            st.subheader(f"Report — {st.session_state.recent_view_title}")
            st.text_area("Report", st.session_state.recent_view_report, height=300)

            # PDF export for historical
            pdf = generate_pdf(st.session_state.recent_view_report)
            st.download_button("📄 Download PDF", pdf, "report.pdf")

            phone = st.text_input("WhatsApp Number","91")
            encoded = urllib.parse.quote(st.session_state.recent_view_report)
            st.markdown(f"[📲 WhatsApp](https://wa.me/{phone}?text={encoded})", unsafe_allow_html=True)

        st.divider()

        # Create new
        if st.button("➕ Create New Statement"):
            st.session_state.create_statement=True
            st.session_state.statement_id=None
            st.session_state.preview=False
            st.session_state.final_report=""
            st.session_state.recent_view_report=""
            st.rerun()

        # Header
        if st.session_state.create_statement and not st.session_state.statement_id:
            uid=user["id"]
            alloc = supabase.table("user_stockists").select("stockist_id").eq("user_id",uid).execute().data
            if alloc:
                stk_ids = [a["stockist_id"] for a in alloc]
                stockists = supabase.table("stockists").select("id,name").in_("id",stk_ids).execute().data
                s_map={s["name"]:s["id"] for s in stockists}
                sel_stockist = st.selectbox("Stockist", list(s_map.keys()))
                year = st.selectbox("Year",[2023,2024,2025])
                month = st.selectbox("Month",MONTHS)
                fd=st.date_input("From",date.today())
                td=st.date_input("To",date.today())

                if st.button("Temporary Submit"):
                    st.session_state.selected_stockist_id = s_map[sel_stockist]
                    st.session_state.stockist_name = sel_stockist
                    st.session_state.sel_month = month
                    st.session_state.sel_year = year
                    st.session_state.current_statement_from_date = fd.isoformat()

                    res = supabase.table("sales_stock_statements").insert({
                        "user_id":uid,
                        "stockist_id":s_map[sel_stockist],
                        "year":year,
                        "month":month,
                        "from_date":fd.isoformat(),
                        "to_date":td.isoformat()
                    }).execute()

                    st.session_state.statement_id=res.data[0]["id"]
                    st.session_state.product_index=0
                    st.session_state.product_data={}
                    st.success("Statement created!")

        # Product Entry
        if st.session_state.statement_id and not st.session_state.preview and not st.session_state.final_report:
            prods = supabase.table("products").select("id,name").order("name").execute().data
            p = prods[st.session_state.product_index]
            last = last_month_data(p["id"])

            st.subheader(f"Product: {p['name']}")

            opening = int(st.number_input("Opening", value=int(last["closing"]), step=1))
            purchase = int(st.number_input("Purchase", value=0, step=1))
            issue = int(st.number_input("Issue", value=0, step=1))
            closing = int(st.number_input("Closing", value=opening, step=1))

            expected = opening + purchase - issue
            diff = expected - closing

            st.session_state.product_data[p["id"]] = {
                "name": p["name"],
                "opening": opening,
                "purchase": purchase,
                "issue": issue,
                "closing": closing,
                "diff": diff,
                "prev_issue": int(last["issue"])
            }

            c1,c2,c3=st.columns(3)
            if c1.button("⬅ Previous") and st.session_state.product_index>0:
                st.session_state.product_index -=1
                st.rerun()
            if c2.button("Next ➡") and st.session_state.product_index < len(prods)-1:
                st.session_state.product_index +=1
                st.rerun()
            if c3.button("Preview"):
                st.session_state.preview=True
                st.rerun()

        # Preview
        if st.session_state.preview and not st.session_state.final_report:
            st.header("Preview")
            rows=[]
            for d in st.session_state.product_data.values():
                rows.append({
                    "Product": d["name"],
                    "Opening": d["opening"],
                    "Purchase": d["purchase"],
                    "Issue": d["issue"],
                    "Closing": d["closing"],
                    "Difference": d["diff"]
                })
            st.table(rows)

            if st.button("Final Submit"):
                for pid,d in st.session_state.product_data.items():
                    supabase.table("sales_stock_items").insert({
                        "statement_id": st.session_state.statement_id,
                        "product_id": pid,
                        "opening": d["opening"],
                        "purchase": d["purchase"],
                        "issue": d["issue"],
                        "closing": d["closing"],
                        "diff_closing": d["diff"]
                    }).execute()

                st.session_state.final_report = build_report(
                    st.session_state.stockist_name,
                    st.session_state.sel_month,
                    st.session_state.sel_year,
                    list(st.session_state.product_data.values())
                )
                st.session_state.preview=False
                st.success("Submitted!")

        # Final Report
        if st.session_state.final_report:
            st.header("Report & Export")
            st.text_area("Report", st.session_state.final_report, height=300)

            # PDF
            pdf = generate_pdf(st.session_state.final_report)
            st.download_button("📄 Download PDF", pdf, "final_report.pdf")

            # WhatsApp
            phone = st.text_input("WhatsApp Number","91")
            encoded = urllib.parse.quote(st.session_state.final_report)
            st.markdown(f"[📲 WhatsApp](https://wa.me/{phone}?text={encoded})", unsafe_allow_html=True)
