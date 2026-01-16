import streamlit as st
from datetime import datetime
from anchors.supabase_client import admin_supabase


def resolve_user_id():
    user = st.session_state.get("auth_user")

    # Supabase user object
    if hasattr(user, "id"):
        return user.id

    # Dict-based test user
    if isinstance(user, dict):
        return user.get("id")

    # Absolute fallback
    return "system"


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
    # OPS FLOW STATE
    # =========================
    if "ops_master_confirmed" not in st.session_state:
        st.session_state.ops_master_confirmed = False

    if "ops_products_done" not in st.session_state:
        st.session_state.ops_products_done = False

    if "ops_submit_done" not in st.session_state:
        st.session_state.ops_submit_done = False



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

        # =========================
        # MASTER FORM (INPUT ONLY)
        # =========================
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
                    "Invoice", "Sample", "Lot", "Destroyed", "Return to Purchaser"
                ]
            else:
                from_options = ["CNF", "User", "Purchaser", "Stockist"]
                to_options = ["Company", "CNF", "User"]
                stock_as_options = ["Purchase", "Credit Note", "Return"]

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

            preview_clicked = st.form_submit_button("Preview")

            if preview_clicked:
                st.session_state.ops_master_confirmed = True

        # =========================
        # AFTER PREVIEW CONFIRMED
        # =========================
        if st.session_state.ops_master_confirmed:

            # ---------- PRODUCT ENGINE ----------
            if "ops_products" not in st.session_state:
                st.session_state.ops_products = []

            if "ops_product_index" not in st.session_state:
                st.session_state.ops_product_index = 0

            st.divider()
            st.subheader("📦 Product Details")

            idx = st.session_state.ops_product_index

            if len(st.session_state.ops_products) <= idx:
                st.session_state.ops_products.append({
                    "product": "",
                    "sale_qty": 0,
                    "free_qty": 0,
                    "total_qty": 0
                })

            current = st.session_state.ops_products[idx]

            product_name = st.text_input(
                "Product",
                value=current["product"],
                key=f"product_{idx}"
            )

            sale_qty = st.number_input(
                "Saleable Quantity",
                min_value=0,
                step=1,
                value=current["sale_qty"],
                key=f"sale_{idx}"
            )

            if stock_as in ["Invoice", "Return", "Credit Note"]:
                free_qty = st.number_input(
                    "Free Quantity",
                    min_value=0,
                    step=1,
                    value=current["free_qty"],
                    key=f"free_{idx}"
                )
            else:
                free_qty = 0

            total_qty = sale_qty + free_qty
            st.info(f"📊 Total Quantity: {total_qty}")

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
                if st.button("⬅ Remove Product") and idx > 0:
                    st.session_state.ops_products.pop()
                    st.session_state.ops_product_index -= 1
                    st.rerun()

            with c3:
                if st.button("✅ End Products"):
                    st.session_state.ops_products_done = True
                    st.rerun()

            # ---------- PREVIEW (AFTER PRODUCTS) ----------
            if st.session_state.ops_products_done:
                st.divider()
                st.subheader("🔍 Preview — Stock Movement")

                st.write("Direction:", stock_direction)
                st.write("From:", from_entity, "-", from_name)
                st.write("To:", to_entity, "-", to_name)
                st.write("Date:", date)
                st.write("Stock As:", stock_as)
                st.write("Reference No:", reference_no)

                st.divider()
                st.subheader("📦 Products")
                for i, p in enumerate(st.session_state.ops_products, start=1):
                    st.write(f"{i}. {p['product']} — Qty: {p['total_qty']}")

                st.divider()

                # ---------- FINAL SUBMIT (TEMP ENABLED) ----------
                if st.button(
                    "✅ Final Submit OPS",
                    type="primary",
                    disabled=st.session_state.ops_submit_done
                ):

                    user_id = resolve_user_id()
                    # ✅ UUID safety check (ADD THIS LINE)
                    if isinstance(user_id, str) and len(user_id) < 36:
                        st.error("❌ Invalid user ID. Please login again.")
                        st.stop()

                    if admin_supabase is None:
                        st.error("❌ Supabase not configured. Contact admin.")
                        st.stop()
                    try:
                        response = admin_supabase.table("ops_documents").insert({
                            "ops_no": f"OPS-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                            "ops_date": date.isoformat(),
                            "ops_type": "ADJUSTMENT",
                            "stock_as": "adjustment",
                            "direction": "ADJUST",
                            "narration": "OPS test submit from UI",
                            "reference_no": reference_no,
                            "created_by": user_id
                        }).execute()

                        ops_document_id = response.data[0]["id"]
                        # ---------- OPS LINES WILL BE INSERTED HERE ----------
                        for p in st.session_state.ops_products:
                            st.info(f"ℹ OPS line ready for product: {p['product']}")

                        st.success("✅ OPS document saved successfully")
                        st.session_state.ops_submit_done = True


                    except Exception as e:
                        st.error("❌ OPS submission failed")
                        st.exception(e)

                if st.session_state.ops_submit_done:
                    st.info("🔒 OPS already submitted. Start a new OPS to continue.")





    # =========================
    # PLACEHOLDERS
    # =========================
    elif section == "ORDERS":
        st.info("🔧 Orders — coming next")

    elif section == "PAYMENTS":
        st.info("🔧 Payments — coming next")
