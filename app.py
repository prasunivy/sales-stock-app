import streamlit as st
from supabase import create_client

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Sales & Stock App", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

# ---------------- FUNCTIONS ----------------
def login(username, password):
    res = (
        supabase.table("users")
        .select("*")
        .eq("username", username)
        .eq("password", password)
        .execute()
    )

    if res.data:
        st.session_state.logged_in = True
        st.session_state.user = res.data[0]
        st.rerun()
    else:
        st.error("Invalid username or password")

def logout():
    st.session_state.clear()
    st.rerun()

# ---------------- UI ----------------
st.title("Sales & Stock Statement App")

# ========== LOGIN ==========
if not st.session_state.logged_in:
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        login(username, password)

# ========== DASHBOARD ==========
else:
    user = st.session_state.user
    st.success(f"Logged in as {user['username']} ({user['role']})")

    if st.button("Logout"):
        logout()

    # ================= ADMIN =================
    if user["role"] == "admin":
        st.header("Admin Dashboard")

        tab1, tab2, tab3, tab4 = st.tabs(
            ["👤 Users", "📦 Products", "🏪 Stockists", "🔗 Allocate Stockists"]
        )

        # USERS
        with tab1:
            u = st.text_input("New Username")
            p = st.text_input("Password", type="password")

            if st.button("Add User"):
                if not u or not p:
                    st.error("Username and password required")
                else:
                    exists = supabase.table("users").select("id").eq("username", u).execute()
                    if exists.data:
                        st.error("Username already exists")
                    else:
                        supabase.table("users").insert(
                            {"username": u, "password": p, "role": "user"}
                        ).execute()
                        st.success("User added")
                        st.rerun()

            st.divider()
            users = supabase.table("users").select("*").execute().data
            for x in users:
                if x["role"] == "user":
                    c1, c2 = st.columns([4,1])
                    c1.write(x["username"])
                    if c2.button("Delete", key=x["id"]):
                        supabase.table("users").delete().eq("id", x["id"]).execute()
                        st.rerun()

        # PRODUCTS
        with tab2:
            prod = st.text_input("Product name")
            if st.button("Add Product"):
                if prod:
                    supabase.table("products").insert({"name": prod}).execute()
                    st.rerun()

            st.divider()
            for p in supabase.table("products").select("*").execute().data:
                c1, c2 = st.columns([4,1])
                c1.write(p["name"])
                if c2.button("Delete", key=p["id"]):
                    supabase.table("products").delete().eq("id", p["id"]).execute()
                    st.rerun()

        # STOCKISTS
        with tab3:
            stk = st.text_input("Stockist name")
            if st.button("Add Stockist"):
                if stk:
                    supabase.table("stockists").insert({"name": stk}).execute()
                    st.rerun()

            st.divider()
            for s in supabase.table("stockists").select("*").execute().data:
                c1, c2 = st.columns([4,1])
                c1.write(s["name"])
                if c2.button("Delete", key=s["id"]):
                    supabase.table("stockists").delete().eq("id", s["id"]).execute()
                    st.rerun()

        # ALLOCATION
        with tab4:
            users = supabase.table("users").select("id, username").eq("role","user").execute().data
            stockists = supabase.table("stockists").select("id, name").execute().data

            if users and stockists:
                u_map = {u["username"]:u["id"] for u in users}
                s_map = {s["name"]:s["id"] for s in stockists}

                sel_user = st.selectbox("User", list(u_map.keys()))
                sel_stk = st.multiselect("Stockists", list(s_map.keys()))

                if st.button("Allocate"):
                    for s in sel_stk:
                        supabase.table("user_stockists").insert(
                            {"user_id": u_map[sel_user], "stockist_id": s_map[s]}
                        ).execute()
                    st.success("Allocated")
                    st.rerun()

            st.divider()
            for a in supabase.table("user_stockists").select("*").execute().data:
                u = supabase.table("users").select("username").eq("id", a["user_id"]).execute().data[0]
                s = supabase.table("stockists").select("name").eq("id", a["stockist_id"]).execute().data[0]
                st.write(f"{u['username']} → {s['name']}")

    # ================= USER =================
    else:
        st.header("User Dashboard")
        st.info("Monthly Sales & Stock Statement will start here (Phase 8)")
