import streamlit as st

def run_ops():
    st.title("📥 Order / Purchase / Sales / Payment")

    role = st.session_state.get("role")
    if role != "admin":
        st.error("❌ You are not authorized to access this module.")
        return

    # ------------------------------
    # OPS INTERNAL NAVIGATION
    # ------------------------------
    st.sidebar.subheader("⚙ OPS Menu")

    if "ops_section" not in st.session_state:
        st.session_state.ops_section = None

    if st.sidebar.button("📦 Opening Stock"):
        st.session_state.ops_section = "OPENING_STOCK"
        st.rerun()

    if st.sidebar.button("💰 Opening Balance"):
        st.session_state.ops_section = "OPENING_BALANCE"
        st.rerun()

    if st.sidebar.button("🔁 Stock In / Stock Out"):
        st.session_state.ops_section = "STOCK_FLOW"
        st.rerun()

    if st.sidebar.button("🧾 Orders"):
        st.session_state.ops_section = "ORDERS"
        st.rerun()

    if st.sidebar.button("💳 Payments"):
        st.session_state.ops_section = "PAYMENTS"
        st.rerun()

    section = st.session_state.ops_section

    # ------------------------------
    # LANDING
    # ------------------------------
    if not section:
        st.info("👈 Select an OPS function from the sidebar")
        return

    # ------------------------------
    # OPENING STOCK (PREVIEW ONLY)
    # ------------------------------
    if section == "OPENING_STOCK":
        st.subheader("📦 Opening Stock (Preview Only)")

        with st.form("opening_stock_form"):
            entity_type = st.selectbox(
                "Select Entity Type",
                ["Company", "CNF", "User", "Stockist"]
            )

            entity_name = st.text_input("Entity Name")
            product = st.text_input("Product Name")
            quantity = st.number_input("Quantity", min_value=0, step=1)

            submitted = st.form_submit_button("Preview")

        if submitted:
            st.markdown("### 🔍 Preview")
            st.write("Entity Type:", entity_type)
            st.write("Entity Name:", entity_name)
            st.write("Product:", product)
            st.write("Quantity:", quantity)

            st.warning("⚠️ Preview only. Data not saved yet.")

    # ------------------------------
    # OPENING BALANCE (PREVIEW ONLY)
    # ------------------------------
    elif section == "OPENING_BALANCE":
        st.subheader("💰 Opening Balance (Preview Only)")

        with st.form("opening_balance_form"):
            entity_type = st.selectbox(
                "Select Entity",
                ["Stockist", "CNF"]
            )

            entity_name = st.text_input("Name")
            amount = st.number_input("Opening Balance Amount", step=1)

            submitted = st.form_submit_button("Preview")

        if submitted:
            st.markdown("### 🔍 Preview")
            st.write("Entity Type:", entity_type)
            st.write("Name:", entity_name)
            st.write("Amount:", amount)

            st.warning("⚠️ Preview only. Data not saved yet.")

    # ------------------------------
    # PLACEHOLDERS (LOCKED FOR NOW)
    # ------------------------------
    elif section == "STOCK_FLOW":
        st.info("🔧 Stock In / Stock Out — coming next")

    elif section == "ORDERS":
        st.info("🔧 Orders — coming next")

    elif section == "PAYMENTS":
        st.info("🔧 Payments — coming next")
