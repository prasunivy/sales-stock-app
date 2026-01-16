import streamlit as st


def run_ops():
    st.title("📥 Order / Purchase / Sales / Payment")

    # =========================
    # ADMIN CHECK
    # =========================
    role = st.session_state.get("role")

    if role != "admin":
        st.error("❌ You are not authorized to access this module.")
        return

    st.success("✅ Admin access granted")

    # =========================
    # OPS INTERNAL NAVIGATION
    # =========================
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

    if not section:
        st.info("👈 Select an OPS function from the sidebar")
        return

    # =========================
    # OPENING STOCK (PREVIEW)
    # =========================
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
            st.warning("⚠️ Preview only. Data not saved.")

    # =========================
    # OPENING BALANCE (PREVIEW)
    # =========================
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
            st.warning("⚠️ Preview only. Data not saved.")

    # =========================
    # STOCK IN / STOCK OUT
    # =========================
    elif section == "STOCK_FLOW":
        st.subheader("🔁 Stock In / Stock Out (Master Form)")

        with st.form("stock_flow_master_form"):
            stock_direction = st.radio(
                "Stock Direction",
                ["Stock Out", "Stock In"],
                horizontal=True
            )

            if stock_direction == "Stock Out":
                from_options = ["Company", "CNF", "User"]
                to_options = ["CNF", "User", "Stockist", "Destroyed", "Purchaser"]
                stock_as_options = [
                    "Invoice",
                    "Sample",
                    "Lot",
                    "Destroyed",
                    "Return to Purchaser"
                ]
            else:
                from_options = ["CNF", "User", "Purchaser", "Stockist"]
                to_options = ["Company", "CNF", "User"]
                stock_as_options = [
                    "Purchase",
                    "Credit Note",
                    "Return"
                ]

            col1, col2 = st.columns(2)

            with col1:
                from_entity = st.selectbox("From", from_options)
                from_name = st.text_input("Name of From")

            with col2:
                to_entity = st.selectbox("To", to_options)
                to_name = st.text_input("Name of To")

            st.divider()

            date = st.date_input("Date")
            stock_as = st.selectbox("Stock As", stock_as_options)
            reference_no = st.text_input("Reference Number")

            submitted = st.form_submit_button("Preview")

        if submitted:
            st.markdown("### 🔍 Preview — Stock Movement")
            st.write("Stock Direction:", stock_direction)
            st.write("From:", from_entity, "-", from_name)
            st.write("To:", to_entity, "-", to_name)
            st.write("Date:", date)
            st.write("Stock As:", stock_as)
            st.write("Reference No:", reference_no)
            st.warning("⚠️ Preview only. Product details not added yet.")

    # =========================
    # PLACEHOLDERS
    # =========================
    elif section == "ORDERS":
        st.info("🔧 Orders — coming next")

    elif section == "PAYMENTS":
        st.info("🔧 Payments — coming next")
