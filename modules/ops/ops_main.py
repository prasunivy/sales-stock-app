import streamlit as st

def run_ops():
    st.title("📥 Order / Purchase / Sales / Payment")

    # =========================
    # ADMIN CHECK (TEMP)
    # =========================
    role = st.session_state.get("role")

    if role != "admin":
        st.error("❌ You are not authorized to access this module.")
        return

    st.success("✅ Admin access granted")

    st.divider()

    # =========================
    # OPENING STOCK – STEP 1
    # =========================
    st.subheader("📦 Opening Stock (Admin Only)")

    with st.form("opening_stock_form"):
        entity_type = st.selectbox(
            "Select Type",
            ["Company", "CNF", "User", "Stockist"]
        )

        entity_name = st.text_input("Name")

        product = st.text_input("Product Name")

        quantity = st.number_input(
            "Quantity",
            min_value=0,
            step=1
        )

        submitted = st.form_submit_button("Preview")

    # =========================
    # PREVIEW (NO SAVE YET)
    # =========================
    if submitted:
        st.subheader("🔍 Preview Opening Stock")

        st.write("**Type:**", entity_type)
        st.write("**Name:**", entity_name)
        st.write("**Product:**", product)
        st.write("**Quantity:**", quantity)

        st.info("⚠️ This is preview only. Data is NOT saved yet.")
