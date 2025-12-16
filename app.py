import streamlit as st
from supabase import create_client

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Sales & Stock App", layout="wide")

# ---------------- SUPABASE ----------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.login_mode = None

# ---------------- FUNCTIONS ----------------
def login_user(username, password):
    res = (
        supabase.table("users")
        .select("*")
        .eq("username", username)
        .eq("password", password)
        .execute()
    )

    if res.data:
        user = res.data[0]
        st.session_state.logged_in = True
        st.session_state.username = user["username"]
        st.session_state.role = user["role"]
        st.experimental_rerun()
    else:
        st.error("Invalid credentials")

def logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.login_mode = None
    st.experimental_rerun()

# ---------------- UI ----------------
st.title("Sales & Stock Statement App")

# ========== LOGIN ==========
if not st.session_state.logged_in:
    st.subheader("Login")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login as Admin"):
            st.session_state.login_mode = "admin"
    with col2:
        if st.button("Login as User"):
            st.session_state.login_mode = "user"

    if st.session_state.login_mode:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            login_user(username, password)

# ========== DASHBOARD ==========
else:
    st.success(
        f"Logged in as {st.session_state.username} ({st.session_state.role})"
    )

    if st.button("Logout"):
        logout()

    # ================= ADMIN =================
    if st.session_state.role == "admin":
        st.header("Admin Dashboard")

        tab1, tab2, tab3, tab4 = st.tabs(
            ["👤 Users", "📦 Products", "🏪 Stockists", "🔗 Allocate Stockists"]
        )

        # ---------- USERS ----------
        with tab1:
            st.subheader("Add User")
            u = st.text_input("Username", key="u")
            p = st.text_input("Password", type="password", key="p")

            if st.button("Add User"):
                if u and p:
                    supabase.table("users").insert(
                        {"username": u, "password": p, "role": "user"}
                    ).execute()
                    st.success("User added")
                    st.experimental_rerun()

            st.divider()
            users = supabase.table("users").select("*").execute().data
            for user in users:
                if user["role"] == "user":
                    c1, c2 = st.columns([3, 1])
                    c1.write(user["username"])
                    if c2.button("Delete", key=user["id"]):
                        supabase.table("users").delete().eq(
                            "id", user["id"]
                        ).execute()
                        st.experimental_rerun()

        # ---------- PRODUCTS ----------
        with tab2:
            st.subheader("Add Product")
            prod = st.text_input("Product name")

            if st.button("Add Product"):
                if prod:
                    supabase.table("products").insert(
                        {"name": prod}
                    ).execute()
                    st.experimental_rerun()

            st.divider()
            products = (
                supabase.table("products")
                .select("*")
                .order("name")
                .execute()
                .data
            )
            for p in products:
                c1, c2 = st.columns([3, 1])
                c1.write(p["name"])
                if c2.button("Delete", key=p["id"]):
                    supabase.table("products").delete().eq(
                        "id", p["id"]
                    ).execute()
                    st.experimental_rerun()

        # ---------- STOCKISTS ----------
        with tab3:
            st.subheader("Add Stockist")
            stk = st.text_input("Stockist name")

            if st.button("Add Stockist"):
                if stk:
                    supabase.table("stockists").insert(
                        {"name": stk}
                    ).execute()
                    st.experimental_rerun()

            st.divider()
            stockists = (
                supabase.table("stockists")
                .select("*")
                .order("name")
                .execute()
                .data
            )
            for s in stockists:
                c1, c2 = st.columns([3, 1])
                c1.write(s["name"])
                if c2.button("Delete", key=s["id"]):
                    supabase.table("stockists").delete().eq(
                        "id", s["id"]
                    ).execute()
                    st.experimental_rerun()

        # ---------- ALLOCATION ----------
        with tab4:
            st.subheader("Allocate Stockists to Users")

            users = (
                supabase.table("users")
                .select("id, username")
                .eq("role", "user")
                .execute()
                .data
            )
            stockists = (
                supabase.table("stockists")
                .select("id, name")
                .execute()
                .data
            )

            user_map = {u["username"]: u["id"] for u in users}
            stk_map = {s["name"]: s["id"] for s in stockists}

            sel_user = st.selectbox("User", list(user_map.keys()))
            sel_stk = st.multiselect("Stockists", list(stk_map.keys()))

            if st.button("Allocate"):
                for s in sel_stk:
                    supabase.table("user_stockists").insert(
                        {
                            "user_id": user_map[sel_user],
                            "stockist_id": stk_map[s],
                        }
                    ).execute()
                st.success("Allocated")
                st.experimental_rerun()

            st.divider()
            allocs = (
                supabase.table("user_stockists")
                .select("id, users(username), stockists(name)")
                .execute()
                .data
            )

            for a in allocs:
                c1, c2 = st.columns([4, 1])
                c1.write(
                    f"{a['users']['username']} → {a['stockists']['name']}"
                )
                if c2.button("Remove", key=a["id"]):
                    supabase.table("user_stockists").delete().eq(
                        "id", a["id"]
                    ).execute()
                    st.experimental_rerun()

    # ================= USER =================
    else:
        st.header("User Dashboard (next step)")
