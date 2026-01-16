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
            # PRODUCT BODY ENGINE (UI)
            # =========================
            if "ops_products" not in st.session_state:
                st.session_state.ops_products = []

            if "ops_product_index" not in st.session_state:
                st.session_state.ops_product_index = 0

            st.divider()
            st.subheader("📦 Product Details")

            current_index = st.session_state.ops_product_index

            # Ensure current product slot exists
            if len(st.session_state.ops_products) <= current_index:
                st.session_state.ops_products.append({
                    "product": "",
                    "sale_qty": 0,
                    "free_qty": 0,
                    "total_qty": 0
                })

            current = st.session_state.ops_products[current_index]

            product_name = st.text_input(
                "Product",
                value=current["product"],
                key=f"ops_product_{current_index}"
            )

            sale_qty = st.number_input(
                "Saleable Quantity",
                min_value=0,
                step=1,
                value=current["sale_qty"],
                key=f"ops_sale_{current_index}"
            )

            # Free quantity only for Invoice / Return / Credit
            if stock_as in ["Invoice", "Return", "Credit Note"]:
                free_qty = st.number_input(
                    "Free Quantity",
                    min_value=0,
                    step=1,
                    value=current["free_qty"],
                    key=f"ops_free_{current_index}"
                )
            else:
                free_qty = 0

            total_qty = sale_qty + free_qty
            st.info(f"📊 Total Quantity: {total_qty}")

            # Update current product
            current.update({
                "product": product_name,
                "sale_qty": sale_qty,
                "free_qty": free_qty,
                "total_qty": total_qty
            })

            st.divider()

            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("➕ Add Product"):
                    st.session_state.ops_product_index += 1
                    st.rerun()

            with c2:
                if st.button("⬅ Remove Product") and current_index > 0:
                    st.session_state.ops_products.pop()
                    st.session_state.ops_product_index -= 1
                    st.rerun()

            with c3:
                if st.button("✅ End Products"):
                    st.session_state.ops_products_done = True
                    st.rerun()

            # =========================
            # PRODUCTS PREVIEW
            # =========================
            if st.session_state.get("ops_products_done"):
                st.divider()
                st.subheader("🔍 Products Preview")

                for i, p in enumerate(st.session_state.ops_products, start=1):
                    st.markdown(
                        f"""
                        **Product {i}**
                        - Name: {p['product']}
                        - Sale Qty: {p['sale_qty']}
                        - Free Qty: {p['free_qty']}
                        - Total Qty: {p['total_qty']}
                        """
                    )

                st.warning("⚠️ Amounts, taxes and final submit will come next.")
                # =========================
                # AMOUNTS ENGINE (UI)
                # =========================
                if stock_as in ["Invoice", "Purchase", "Return", "Credit Note"]:
                    st.divider()
                    st.subheader("💰 Amount Details")

                    if "ops_amounts" not in st.session_state:
                        st.session_state.ops_amounts = {
                            "gross": 0,
                            "tax": 0,
                            "discount": 0,
                            "net": 0
                        }

                    gross = st.number_input(
                        "Gross Amount",
                        min_value=0.0,
                        step=1.0,
                        value=st.session_state.ops_amounts["gross"]
                    )

                    tax = st.number_input(
                        "Tax Amount",
                        min_value=0.0,
                        step=1.0,
                        value=st.session_state.ops_amounts["tax"]
                    )

                    discount = st.number_input(
                        "Discount (Optional)",
                        min_value=0.0,
                        step=1.0,
                        value=st.session_state.ops_amounts["discount"]
                    )

                    net = gross + tax - discount

                    st.metric("Net Amount", f"{net:.2f}")

                    st.session_state.ops_amounts.update({
                        "gross": gross,
                        "tax": tax,
                        "discount": discount,
                        "net": net
                    })

                    st.info("ℹ️ Net Amount = Gross + Tax − Discount")
                    # =========================
                    # FINAL PREVIEW GATE (UI ONLY)
                    # =========================
                    st.divider()
                    st.subheader("🔍 Final Preview (Read-only)")

                    st.markdown("#### 📦 Movement Summary")
                    st.write("**Direction:**", stock_direction)
                    st.write("**From:**", from_entity, "-", from_name)
                    st.write("**To:**", to_entity, "-", to_name)
                    st.write("**Date:**", date)
                    st.write("**Stock As:**", stock_as)
                    st.write("**Reference No:**", reference_no)

                    st.divider()
                    st.markdown("#### 📦 Products")
                    for i, p in enumerate(st.session_state.get("ops_products", []), start=1):
                        st.markdown(
                            f"""
                            **Product {i}**
                            - Name: {p.get('product')}
                            - Sale Qty: {p.get('sale_qty')}
                            - Free Qty: {p.get('free_qty')}
                            - Total Qty: {p.get('total_qty')}
                            """
                        )

                    if stock_as in ["Invoice", "Purchase", "Return", "Credit Note"]:
                        st.divider()
                        st.markdown("#### 💰 Amounts")
                        a = st.session_state.get("ops_amounts", {})
                        st.write("Gross:", a.get("gross"))
                        st.write("Tax:", a.get("tax"))
                        st.write("Discount:", a.get("discount"))
                        st.write("Net:", a.get("net"))

                    st.divider()
                    st.button("🚫 Final Submit (Disabled – UI Only)", disabled=True)
                    st.caption("Final submit will be enabled after DB wiring & validations.")
                    # =========================
                    # VALIDATION CHECKS (UI ONLY)
                    # =========================
                    st.divider()
                    st.subheader("✅ Validation Checklist (Read-only)")

                    validations = []

                    # Basic master validations
                    validations.append((
                        "From / To selected",
                        bool(from_entity and to_entity and from_name and to_name)
                    ))

                    validations.append((
                        "Stock As selected",
                        bool(stock_as)
                    ))

                    validations.append((
                        "At least one product added",
                        len(st.session_state.get("ops_products", [])) > 0
                    ))

                    # Product-level validation
                    all_products_valid = True
                    for p in st.session_state.get("ops_products", []):
                        if not p.get("product") or p.get("total_qty", 0) <= 0:
                            all_products_valid = False
                            break

                    validations.append((
                        "All products have name & quantity",
                        all_products_valid
                    ))

                    # Amount validation (only when required)
                    if stock_as in ["Invoice", "Purchase", "Return", "Credit Note"]:
                        a = st.session_state.get("ops_amounts", {})
                        validations.append((
                            "Net amount calculated",
                            a.get("net", 0) > 0
                        ))

                    # Display validations
                    all_passed = True
                    for label, passed in validations:
                        if passed:
                            st.success(f"✅ {label}")
                        else:
                            st.error(f"❌ {label}")
                            all_passed = False

                    if not all_passed:
                        st.warning("⚠️ Fix the above items before final submit is enabled.")
                    else:
                        st.info("ℹ️ All validations passed. Submit will be enabled in next phase.")




    # =========================
    # PLACEHOLDERS
    # =========================
    elif section == "ORDERS":
        st.info("🔧 Orders — coming next")

    elif section == "PAYMENTS":
        st.info("🔧 Payments — coming next")
