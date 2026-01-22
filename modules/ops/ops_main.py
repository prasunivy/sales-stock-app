import streamlit as st
from datetime import datetime
from anchors.supabase_client import admin_supabase
# ---------- Helper: resolve entity display name ----------
def resolve_entity_name(entity_type, entity_id):
    if entity_type == "Company":
        return "Company"

    if entity_type == "CNF":
        return next(
            (c["name"] for c in st.session_state.cnfs_master if c["id"] == entity_id),
            "Unknown CNF"
        )

    if entity_type == "User":
        return next(
            (u["username"] for u in st.session_state.users_master if u["id"] == entity_id),
            "Unknown User"
        )

    if entity_type == "Stockist":
        return next(
            (s["name"] for s in st.session_state.stockists_master if s["id"] == entity_id),
            "Unknown Stockist"
        )

    if entity_type == "Purchaser":
        return next(
            (p["name"] for p in st.session_state.purchasers_master if p["id"] == entity_id),
            "Unknown Purchaser"
        )

    if entity_type == "Destroyed":
        return "Destroyed"

    return "Unknown"



def resolve_user_id():
    """
    Always returns a valid users.id.
    In TEST MODE, safely falls back to the first admin user.
    """
    user = st.session_state.get("auth_user")

    # Real Supabase-auth user
    if hasattr(user, "id"):
        return user.id

    # TEST MODE fallback — get one admin from users table
    try:
        resp = admin_supabase.table("users") \
            .select("id") \
            .eq("role", "admin") \
            .limit(1) \
            .execute()

        if resp.data:
            return resp.data[0]["id"]
    except Exception:
        pass

    st.error("❌ No valid admin user found in users table")
    st.stop()


def run_ops():
    if "ops_flow_stage" not in st.session_state:
        st.session_state.ops_flow_stage = "LINE1"
    if "ops_allow_reset" not in st.session_state:
        st.session_state.ops_allow_reset = False


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
    # MASTER DATA CACHE (FAST)
    # =========================

    # USERS
    if "users_master" not in st.session_state:
        users_resp = admin_supabase.table("users") \
            .select("id, username") \
            .order("username") \
            .execute()
        st.session_state.users_master = users_resp.data or []

    # CNFS
    if "cnfs_master" not in st.session_state:
        cnf_resp = admin_supabase.table("cnfs") \
            .select("id, name") \
            .order("name") \
            .execute()
        st.session_state.cnfs_master = cnf_resp.data or []

    # STOCKISTS
    if "stockists_master" not in st.session_state:
        stockist_resp = admin_supabase.table("stockists") \
            .select("id, name") \
            .order("name") \
            .execute()
        st.session_state.stockists_master = stockist_resp.data or []

    # PURCHASERS
    if "purchasers_master" not in st.session_state:
        purchaser_resp = admin_supabase.table("purchasers") \
            .select("id, name, email") \
            .order("name") \
            .execute()
        st.session_state.purchasers_master = purchaser_resp.data or []

    # PRODUCTS
    if "products_master" not in st.session_state:
        product_resp = admin_supabase.table("products") \
            .select("id, name") \
            .order("name") \
            .execute()
        st.session_state.products_master = product_resp.data or []

        # CNF → USER MAPPING CACHE
        if "cnf_user_map" not in st.session_state:
            resp = admin_supabase.table("cnf_users") \
                .select("cnf_id, user_id") \
                .execute()
            st.session_state.cnf_user_map = resp.data or []

        # USER → STOCKIST MAPPING CACHE
        if "user_stockist_map" not in st.session_state:
            resp = admin_supabase.table("user_stockists") \
                .select("user_id, stockist_id") \
                .execute()
            st.session_state.user_stockist_map = resp.data or []


    # =========================
    # OPS FLOW STATE
    # =========================
    # ---------- LINE-2 STEPWISE STATE ----------
    if "ops_line2_phase" not in st.session_state:
        st.session_state.ops_line2_phase = 1
        # 0 = not started
        # 1 = from selected, waiting save
        # 2 = to selection active

    if "ops_from_entity_id" not in st.session_state:
        st.session_state.ops_from_entity_id = None

    if "ops_from_entity_type" not in st.session_state:
        st.session_state.ops_from_entity_type = None

    if "ops_to_entity_id" not in st.session_state:
        st.session_state.ops_to_entity_id = None

    if "ops_to_entity_type" not in st.session_state:
        st.session_state.ops_to_entity_type = None

    if "ops_line2_complete" not in st.session_state:
        st.session_state.ops_line2_complete = False

    if "ops_line3_complete" not in st.session_state:
        st.session_state.ops_line3_complete = False


    
    if "ops_master_confirmed" not in st.session_state:
        st.session_state.ops_master_confirmed = False

    if "ops_products_done" not in st.session_state:
        st.session_state.ops_products_done = False

    if "ops_amounts" not in st.session_state:
        st.session_state.ops_amounts = None

    
    if "ops_submit_done" not in st.session_state:
        st.session_state.ops_submit_done = False

    if "purchaser_edit_mode" not in st.session_state:
        st.session_state.purchaser_edit_mode = False

    if "editing_purchaser_id" not in st.session_state:
        st.session_state.editing_purchaser_id = None


    if "cnf_user_edit_mode" not in st.session_state:
        st.session_state.cnf_user_edit_mode = False
    # =========================
    # BUSINESS-CORRECT ROUTE MATRIX (LINE-1)    
    # =========================

    # STOCK OUT — GOODS GOING OUT
    STOCK_OUT_ROUTES = {
        "Company": ["CNF", "User", "Stockist", "Purchaser", "Destroyed"],
        "CNF": ["Company", "User", "Stockist"],
        "User": ["Company", "CNF", "Stockist"],
        "Stockist": ["Company", "CNF", "User", "Purchaser"],
        "Purchaser": ["Company"],
        "Destroyed": []
    }
    # STOCK IN — AUTO-DERIVED (REVERSE OF STOCK OUT, DESTROYED EXCLUDED)
    STOCK_IN_ROUTES = {}

    for from_entity, to_entities in STOCK_OUT_ROUTES.items():
        for to_entity in to_entities:
            # Destroyed is outbound-only
            if to_entity == "Destroyed" or from_entity == "Destroyed":
                continue

            # Reverse the direction
            STOCK_IN_ROUTES.setdefault(to_entity, []).append(from_entity)

    # Ensure all known entities exist as keys
    for entity in STOCK_OUT_ROUTES.keys():
        STOCK_IN_ROUTES.setdefault(entity, [])

    

    
    # ---------- LINE-1 TYPE TRACKING ----------
    if "ops_line1_from_type" not in st.session_state:
        st.session_state.ops_line1_from_type = None

    if "ops_line1_to_type" not in st.session_state:
        st.session_state.ops_line1_to_type = None


    



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

    if st.sidebar.button("🏢 CNF Master"):
        st.session_state.ops_section = "CNF_MASTER"
        st.rerun()

    if st.sidebar.button("🔗 CNF–User Mapping"):
        st.session_state.ops_section = "CNF_USER_MAPPING"
        st.rerun()

    if st.sidebar.button("🏭 Purchaser Master"):
        st.session_state.ops_section = "PURCHASER_MASTER"
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
        # 🔓 POST-SUBMIT ACTIONS (SHOWN FIRST)
        if st.session_state.ops_submit_done:
            st.success("✅ OPS Submitted Successfully")
            
            if "ops_master_payload" in st.session_state:
                with st.expander("📋 View OPS Details"):
                    st.json(st.session_state.ops_master_payload)
            
            st.divider()
            st.subheader("🛠 What would you like to do next?")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("➕ New OPS", type="primary", key="new_ops_btn"):
                    # Reset everything
                    st.session_state.ops_submit_done = False
                    st.session_state.ops_allow_reset = False
                    st.session_state.ops_flow_stage = "LINE1"
                    st.session_state.ops_line1_from_type = None
                    st.session_state.ops_line1_to_type = None
                    st.session_state.ops_line2_phase = 1
                    st.session_state.ops_line2_complete = False
                    st.session_state.ops_line3_complete = False
                    st.session_state.ops_from_entity_type = None
                    st.session_state.ops_from_entity_id = None
                    st.session_state.ops_to_entity_type = None
                    st.session_state.ops_to_entity_id = None
                    st.session_state.ops_master_confirmed = False
                    st.session_state.ops_products_done = False
                    st.session_state.ops_products = []
                    st.session_state.ops_product_index = 0
                    st.session_state.ops_amounts = None
                    st.session_state.ops_delete_confirm = False
                    st.rerun()
            
            with col2:
                if "ops_delete_confirm" not in st.session_state:
                    st.session_state.ops_delete_confirm = False
                
                if not st.session_state.ops_delete_confirm:
                    if st.button("🗑 Delete This OPS", type="secondary", key="delete_btn"):
                        st.session_state.ops_delete_confirm = True
                        st.rerun()
                else:
                    st.warning("⚠️ This will permanently delete the OPS. Confirm?")
                    
                    col_no, col_yes = st.columns(2)
                    
                    with col_no:
                        if st.button("❌ No, Cancel", key="cancel_btn"):
                            st.session_state.ops_delete_confirm = False
                            st.rerun()
                    
                    with col_yes:
                        if st.button("✅ Yes, Delete", type="primary", key="confirm_btn"):
                            try:
                                if "last_ops_document_id" in st.session_state:
                                    ops_id = st.session_state.last_ops_document_id
                                    user_id = resolve_user_id()
                                    
                                    # Audit log
                                    admin_supabase.table("audit_logs").insert({
                                        "action": "DELETE_OPS",
                                        "target_type": "ops_documents",
                                        "target_id": ops_id,
                                        "performed_by": user_id,
                                        "message": "OPS deleted by admin",
                                        "metadata": {"ops_document_id": ops_id}
                                    }).execute()
                                    
                                    # Delete records
                                    admin_supabase.table("financial_ledger").delete().eq("ops_document_id", ops_id).execute()
                                    admin_supabase.table("stock_ledger").delete().eq("ops_document_id", ops_id).execute()
                                    admin_supabase.table("ops_lines").delete().eq("ops_document_id", ops_id).execute()
                                    admin_supabase.table("ops_documents").delete().eq("id", ops_id).execute()
                                    
                                    st.success("✅ OPS deleted successfully")
                                    
                                    # Reset everything
                                    st.session_state.ops_submit_done = False
                                    st.session_state.ops_delete_confirm = False
                                    st.session_state.ops_flow_stage = "LINE1"
                                    st.session_state.ops_line1_from_type = None
                                    st.session_state.ops_line1_to_type = None
                                    st.session_state.ops_line2_phase = 1
                                    st.session_state.ops_line2_complete = False
                                    st.session_state.ops_line3_complete = False
                                    st.session_state.ops_from_entity_type = None
                                    st.session_state.ops_from_entity_id = None
                                    st.session_state.ops_to_entity_type = None
                                    st.session_state.ops_to_entity_id = None
                                    st.session_state.ops_master_confirmed = False
                                    st.session_state.ops_products_done = False
                                    st.session_state.ops_products = []
                                    st.session_state.ops_product_index = 0
                                    st.session_state.ops_amounts = None
                                    
                                    st.rerun()
                                else:
                                    st.error("❌ OPS ID not found")
                            
                            except Exception as e:
                                st.error("❌ Failed to delete OPS")
                                st.exception(e)
            
            st.stop()

        st.subheader("🔁 Stock In / Stock Out (Master Form)")

        # =========================
        # MASTER INPUT (NO FORM)
        # =========================
        if st.session_state.ops_flow_stage == "LINE1":
            stock_direction = st.radio(
                "Stock Direction",
                ["Stock Out", "Stock In"],
                horizontal=True
            )
            # ✅ DEFINE STOCK AS OPTIONS EARLY (STREAMLIT SAFE)
            if stock_direction == "Stock Out":
                stock_as_options = [
                    "Invoice", "Sample", "Lot", "Destroyed", "Return to Purchaser"
                ]
            else:
                stock_as_options = [
                    "Purchase", "Credit Note", "Return"
                ]

        # Line-1 entity universe
        # 🔒 LOCK LINE-1 AFTER LINE-2 STARTS
        # 🔒 LOCK LINE-1 ONLY AFTER LINE-2 IS COMPLETE
        line1_locked = st.session_state.ops_line2_complete is True


        from_options = ["Company", "CNF", "User", "Stockist", "Purchaser"]

        col1, col2 = st.columns(2)

        with col1:
            from_entity = st.selectbox(
                "From Entity Type",
                from_options,
                disabled=line1_locked
            )

        # ✅ Now from_entity EXISTS — safe to compute routes
        if stock_direction == "Stock Out":
            to_options = STOCK_OUT_ROUTES.get(from_entity, [])
        else:
            to_options = STOCK_IN_ROUTES.get(from_entity, [])

        with col2:
            to_entity = st.selectbox(
                "To Entity Type",
                to_options,
                disabled=line1_locked
            )


        # 🔁 RESET LINE-2 ONLY WHEN LINE-1 TYPE CHANGES
        if (
            st.session_state.ops_line1_from_type != from_entity
            or st.session_state.ops_line1_to_type != to_entity
        ):
            st.session_state.ops_line1_from_type = from_entity
            st.session_state.ops_line1_to_type = to_entity

            st.session_state.ops_line2_phase = 1
            st.session_state.ops_line2_complete = False
            st.session_state.ops_line3_complete = False

            st.session_state.ops_from_entity_id = None
            st.session_state.ops_from_entity_type = None
            st.session_state.ops_to_entity_id = None
            st.session_state.ops_to_entity_type = None

        
        


        st.divider()
        # =========================
        # LINE-2 : STEPWISE INSTANCE SELECTION
        # =========================

        
        
        # ---------- LINE-2A : FROM (ACTUAL) ----------
        if not st.session_state.ops_line2_complete:

            st.subheader("🔹 From (Actual Entity)")

            if from_entity == "Company":
                if st.button("Confirm Company"):
                    st.session_state.ops_from_entity_type = "Company"
                    st.session_state.ops_from_entity_id = None
                    st.session_state.ops_line2_complete = True
                    st.rerun()

            elif from_entity == "CNF":
                cnf_map = {c["name"]: c["id"] for c in st.session_state.cnfs_master}
                selected = st.selectbox("Select CNF", list(cnf_map.keys()))
                if st.button("Confirm CNF"):
                    st.session_state.ops_from_entity_type = "CNF"
                    st.session_state.ops_from_entity_id = cnf_map[selected]
                    st.session_state.ops_line2_complete = True
                    st.rerun()

            elif from_entity == "User":
                user_map = {u["username"]: u["id"] for u in st.session_state.users_master}
                selected = st.selectbox("Select User", list(user_map.keys()))
                if st.button("Confirm User"):
                    st.session_state.ops_from_entity_type = "User"
                    st.session_state.ops_from_entity_id = user_map[selected]
                    st.session_state.ops_line2_complete = True
                    st.rerun()

            elif from_entity == "Stockist":
                stockist_map = {s["name"]: s["id"] for s in st.session_state.stockists_master}
                selected = st.selectbox("Select Stockist", list(stockist_map.keys()))
                if st.button("Confirm Stockist"):
                    st.session_state.ops_from_entity_type = "Stockist"
                    st.session_state.ops_from_entity_id = stockist_map[selected]
                    st.session_state.ops_line2_complete = True
                    st.rerun()

            st.stop()


        def get_stockists_visible_to_cnf(cnf_id):
            # Users under this CNF
            user_ids = [
                m["user_id"]
                for m in st.session_state.cnf_user_map
                if m["cnf_id"] == cnf_id
            ]

            # Stockists under those users
            stockist_ids = [
                m["stockist_id"]
                for m in st.session_state.user_stockist_map
                if m["user_id"] in user_ids
            ]

            return stockist_ids
            
        

        # =========================
        # LINE-3 : TO (ACTUAL ENTITY)
        # =========================

        if st.session_state.ops_line2_complete and not st.session_state.ops_line3_complete:

            st.subheader("🔹 To (Actual Entity)")

            dest_map = {}
            from_type = st.session_state.ops_from_entity_type
            from_id = st.session_state.ops_from_entity_id

            if to_entity == "Company":
                dest_map = {"Company": None}

            elif to_entity == "CNF":
                dest_map = {c["name"]: c["id"] for c in st.session_state.cnfs_master}

            elif to_entity == "User":
                dest_map = {u["username"]: u["id"] for u in st.session_state.users_master}

            elif to_entity == "Stockist":
                dest_map = {s["name"]: s["id"] for s in st.session_state.stockists_master}

            elif to_entity == "Purchaser":
                dest_map = {p["name"]: p["id"] for p in st.session_state.purchasers_master}

            elif to_entity == "Destroyed":
                if st.button("Confirm Destruction"):
                    st.session_state.ops_to_entity_type = "Destroyed"
                    st.session_state.ops_to_entity_id = None
                    st.session_state.ops_line3_complete = True
                    st.rerun()

            if dest_map:
                selected = st.selectbox("Select Destination", list(dest_map.keys()))
                if st.button("Confirm Destination"):
                    st.session_state.ops_to_entity_type = to_entity
                    st.session_state.ops_to_entity_id = dest_map[selected]
                    st.session_state.ops_line3_complete = True
                    st.rerun()

            st.stop()




        if not (
            st.session_state.ops_line2_complete
            and st.session_state.ops_line3_complete
        ):
            st.warning("⛔ Complete entity binding (From → To) to continue")
            st.stop()

        if st.button("🔄 Reset Entity Selection"):
            st.session_state.ops_line2_complete = False
            st.session_state.ops_line3_complete = False
            st.session_state.ops_from_entity_type = None
            st.session_state.ops_from_entity_id = None
            st.session_state.ops_to_entity_type = None
            st.session_state.ops_to_entity_id = None
            st.session_state.ops_master_confirmed = False
            st.rerun()

        date = st.date_input("Date")

        stock_as = st.selectbox("Stock As", stock_as_options)
        reference_no = st.text_input("Reference Number")

        preview_clicked = st.button("Preview")

        if preview_clicked:
            st.session_state.ops_master_confirmed = True

        
        # =========================
        # AFTER PREVIEW CONFIRMED
        # =========================
        if st.session_state.ops_master_confirmed:
            from_display = resolve_entity_name(
                st.session_state.ops_from_entity_type,
                st.session_state.ops_from_entity_id
                
            )

            to_display = resolve_entity_name(
                st.session_state.ops_to_entity_type,
                st.session_state.ops_to_entity_id
                
            )

            # =========================
            # BUILD OPS MASTER PAYLOAD
            # =========================
            ops_master = {
                "stock_direction": stock_direction,

                "from_entity_type": st.session_state.ops_from_entity_type,
                "from_entity_name": from_display,
                "from_entity_id": st.session_state.ops_from_entity_id,

                "to_entity_type": st.session_state.ops_to_entity_type,
                "to_entity_name": to_display,
                "to_entity_id": st.session_state.ops_to_entity_id,

                "stock_as": stock_as,
                "reference_no": reference_no,
                "date": str(date)
            }


            st.session_state.ops_master_payload = ops_master
            st.subheader("🔍 OPS Master Payload (Preview)")
            st.json(st.session_state.ops_master_payload)
            if st.button("🔄 Reset OPS Master Details"):
                st.session_state.ops_master_confirmed = False
                st.session_state.ops_products_done = False
                st.session_state.ops_products = []
                st.session_state.ops_product_index = 0
                st.rerun()




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

            product_map = {
                p["name"]: p["id"]
                for p in st.session_state.products_master
            }

            selected_product = st.selectbox(
                "Product",
                list(product_map.keys()),
                key=f"product_select_{st.session_state.ops_product_index}"
            )

            product_id = product_map[selected_product]

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
                "product": selected_product,
                "product_id": product_id,
                "sale_qty": sale_qty,
                "free_qty": free_qty,
                "total_qty": total_qty
            })


            st.divider()
            c1, c2, c3 = st.columns(3)

            with c1:
                if st.button("➕ Add Product"):
                    st.session_state.ops_product_index += 1
                    st.session_state.ops_products.append({
                        "product": "",
                        "product_id": None,
                        "sale_qty": 0,
                        "free_qty": 0,
                        "total_qty": 0
                    })
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
                


                from_display = resolve_entity_name(
                    st.session_state.ops_from_entity_type,
                    st.session_state.ops_from_entity_id
                )

                to_display = resolve_entity_name(
                    st.session_state.ops_to_entity_type,
                    st.session_state.ops_to_entity_id
                )

                st.write("From:", st.session_state.ops_from_entity_type, "-", from_display)
                st.write("To:", st.session_state.ops_to_entity_type, "-", to_display)

                st.write("Date:", date)
                st.write("Stock As:", stock_as)
                st.write("Reference No:", reference_no)

                st.divider()
                st.subheader("📦 Products")
                for i, p in enumerate(st.session_state.ops_products, start=1):
                    st.write(f"{i}. {p['product']} — Qty: {p['total_qty']}")

                st.divider()
                # =========================
                # DOCUMENT LEVEL AMOUNTS
                # =========================
                st.subheader("💰 Document Amounts")

                if st.session_state.ops_amounts is None:

                    gross_amt = st.number_input(
                        "Gross Amount",
                        min_value=0.0,
                        step=0.01
                    )

                    tax_amt = st.number_input(
                        "Tax Amount",
                        min_value=0.0,
                        step=0.01
                    )

                    discount_amt = st.number_input(
                        "Discount Amount (Optional)",
                        min_value=0.0,
                        step=0.01
                    )

                    net_amt = st.number_input(
                        "Net Amount",
                        min_value=0.0,
                        step=0.01
                    )

                    if st.button("💾 Save & Next"):
                        st.session_state.ops_amounts = {
                            "gross": gross_amt,
                            "tax": tax_amt,
                            "discount": discount_amt,
                            "net": net_amt
                        }
                        st.rerun()
                # =========================
                # FINAL PREVIEW — AMOUNTS
                # =========================
                if st.session_state.ops_amounts:

                    st.divider()
                    st.subheader("🔍 Final Preview — Stock + Accounts")

                    
                    # =========================
                    # 📲 WHATSAPP PREVIEW (NO DB) — OPTION B
                    # =========================
                    a = st.session_state.ops_amounts

                    narration_text = ops_master.get("narration", "-")

                    whatsapp_text = (
                        f"OPS PREVIEW\n"
                        f"From: {from_display}\n"
                        f"To: {to_display}\n"
                        f"Date: {date}\n"
                        f"Reference: {reference_no}\n\n"
                        f"Stock As: {stock_as}\n"
                        f"Narration: {narration_text}\n\n"
                        f"Products:\n"
                        + "\n".join(
                            [f"- {p['product']} : {p['total_qty']}" for p in st.session_state.ops_products]
                        )
                        + f"\n\nNet Amount: {a['net']}"
                    )


                    whatsapp_url = (
                        "https://wa.me/?text="
                        + whatsapp_text.replace(" ", "%20").replace("\n", "%0A")
                    )

                    st.markdown(
                        f"[📲 Send on WhatsApp]({whatsapp_url})",
                        unsafe_allow_html=True
                    )


                    st.write("Gross Amount:", a["gross"])
                    st.write("Tax Amount:", a["tax"])
                    st.write("Discount:", a["discount"])
                    st.write("Net Amount:", a["net"])

                    
                    
                    if st.button("✏️ Edit Amounts"):
                        st.session_state.ops_amounts = None
                        st.rerun()


                                

                # ---------- FINAL SUBMIT (TEMP ENABLED) ----------

                if st.button("🔄 Reset Products"):
                    st.session_state.ops_products = []
                    st.session_state.ops_product_index = 0
                    st.session_state.ops_products_done = False
                    st.rerun()

                
                if st.button(
                    "✅ Final Submit OPS",
                    type="primary",
                    disabled=st.session_state.ops_submit_done or st.session_state.ops_amounts is None

                ):
                    # 🔒 SAFETY — Amounts must be saved before submit
                    if st.session_state.ops_amounts is None:
                        st.error("❌ Please enter amounts and click 'Save & Next' before Final Submit.")
                        st.stop()


                    user_id = resolve_user_id()
                    # ✅ UUID safety check (ADD THIS LINE)
                    if isinstance(user_id, str) and len(user_id) < 36:
                        st.error("❌ Invalid user ID. Please login again.")
                        st.stop()

                    if admin_supabase is None:
                        st.error("❌ Supabase not configured. Contact admin.")
                        st.stop()
                    # 🔒 SAFETY CHECK — Line-2 must be bound
                    if not all([
                        st.session_state.ops_from_entity_type,
                        st.session_state.ops_to_entity_type
                    ]):
                        st.error("❌ OPS entity binding incomplete. Please restart OPS.")
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
                        st.session_state.last_ops_document_id = ops_document_id  
                        # ---------- INSERT OPS LINES ----------
                        for p in st.session_state.ops_products:
                            a = st.session_state.ops_amounts


                            # 🔎 Resolve product_id from products master
                            product_resp = admin_supabase.table("products") \
                                .select("id") \
                                .eq("name", p["product"]) \
                                .limit(1) \
                                .execute()

                            if not product_resp.data:
                                st.error(f"❌ Product not found in master: {p['product']}")
                                st.stop()

                            

                            admin_supabase.table("ops_lines").insert({
                                "ops_document_id": ops_document_id,
                                "product_id": p["product_id"],

                                # Operator-entered quantities (NO calculations)
                                "sale_qty": p.get("sale_qty", 0),
                                "free_qty": p.get("free_qty", 0),

                                # Operator-entered financials (NO calculations)
                                "gross_amount": a["gross"],
                                "tax_amount": a["tax"],
                                "discount_amount": a["discount"],
                                "net_amount": a["net"],
                                "net_rate": 0,


                                "line_narration": "OPS stock flow entry"
                            }).execute()
                        
                        # ---------- FINANCIAL LEDGER INSERT ----------
                        a = st.session_state.ops_amounts
                        net = a["net"]

                        debit = net if net > 0 else 0
                        credit = abs(net) if net < 0 else 0
                        # ---------- LEDGER PARTY SAFETY ----------
                        party_id = (
                            None
                            if st.session_state.ops_to_entity_type == "Company"
                            else st.session_state.ops_to_entity_id
                        )


                        admin_supabase.table("financial_ledger").insert({
                            "ops_document_id": ops_document_id,
                            "party_id": party_id,
                            "txn_date": date.isoformat(),
                            "debit": debit,
                            "credit": credit,
                            "closing_balance": 0,
                            "narration": "OPS stock posting"
                        }).execute()




                        st.success("✅ OPS document saved successfully")
                        st.session_state.ops_submit_done = True

                        



                        





                    except Exception as e:
                        st.error("❌ OPS submission failed")
                        st.exception(e)

                






    # =========================
    # PLACEHOLDERS
    # =========================
    # =========================
    # CNF MASTER (ADMIN ONLY)
    # =========================
    elif section == "CNF_MASTER":
        st.subheader("🏢 CNF Master")

        # ---------- LOAD CNFS (CACHED) ----------
        if "cnf_master" not in st.session_state:
            cnf_resp = admin_supabase.table("cnfs") \
                .select("id, name, state, is_active") \
                .order("name") \
                .execute()
            st.session_state.cnf_master = cnf_resp.data or []

        # ---------- ADD CNF FORM ----------
        with st.form("add_cnf_form"):
            cnf_name = st.text_input("CNF Name")
            cnf_state = st.text_input("State")
            save_cnf = st.form_submit_button("➕ Add CNF")

        if save_cnf:
            if not cnf_name.strip():
                st.error("CNF name is required")
                st.stop()

            try:
                admin_supabase.table("cnfs").insert({
                    "name": cnf_name.strip(),
                    "state": cnf_state.strip(),
                    "created_by": resolve_user_id()
                }).execute()

                st.success("✅ CNF added successfully")
                st.session_state.pop("cnf_master", None)
                st.rerun()

            except Exception as e:
                st.error("❌ CNF already exists or error occurred")
                st.exception(e)

        # ---------- SHOW CNF LIST ----------
        st.divider()
        st.subheader("📋 Existing CNFs")

        if not st.session_state.cnf_master:
            st.info("No CNFs found")
        else:
            for cnf in st.session_state.cnf_master:
                col1, col2, col3 = st.columns([4, 3, 2])

                with col1:
                    st.write(cnf["name"])

                with col2:
                    st.write(cnf["state"] or "-")

                with col3:
                    status = "✅ Active" if cnf["is_active"] else "🚫 Inactive"
                    st.write(status)

    # =========================
    # CNF ↔ USER MAPPING (ADMIN ONLY)
    # =========================
    elif section == "CNF_USER_MAPPING":
        st.subheader("🔗 CNF – User Mapping")

        col_edit, col_spacer = st.columns([2, 8])

        with col_edit:
            if not st.session_state.cnf_user_edit_mode:
                if st.button("✏️ Edit Mapping"):
                    st.session_state.cnf_user_edit_mode = True
                    st.rerun()
            else:
                if st.button("❌ Cancel Edit"):
                    st.session_state.cnf_user_edit_mode = False
                    st.rerun()


        # ---------- LOAD CNFS ----------
        cnf_resp = admin_supabase.table("cnfs") \
            .select("id, name") \
            .order("name") \
            .execute()
        cnfs = cnf_resp.data or []

        if not cnfs:
            st.warning("No CNFs found. Please create CNFs first.")
            st.stop()

        cnf_map = {c["name"]: c["id"] for c in cnfs}

        selected_cnf_name = st.selectbox(
            "Select CNF",
            options=list(cnf_map.keys())
        )

        selected_cnf_id = cnf_map[selected_cnf_name]

        st.divider()

        # ---------- LOAD USERS ----------
        users_resp = admin_supabase.table("users") \
            .select("id, username") \
            .order("username") \
            .execute()
        users = users_resp.data or []

        if not users:
            st.warning("No users found.")
            st.stop()

        user_map = {u["username"]: u["id"] for u in users}

        # ---------- EXISTING MAPPINGS ----------
        mapping_resp = admin_supabase.table("cnf_users") \
            .select("user_id") \
            .eq("cnf_id", selected_cnf_id) \
            .execute()

        mapped_user_ids = {m["user_id"] for m in (mapping_resp.data or [])}

        default_users = [
            name for name, uid in user_map.items()
            if uid in mapped_user_ids
        ]

        # ---------- MULTISELECT ----------
        selected_users = st.multiselect(
            "Assigned Users",
            options=list(user_map.keys()),
            default=default_users,
            disabled=not st.session_state.cnf_user_edit_mode
        )


        # ---------- SAVE BUTTON ----------
        if st.session_state.cnf_user_edit_mode:
            if st.button("💾 Save CNF–User Mapping"):
                try:
                    # Remove old mappings for this CNF
                    admin_supabase.table("cnf_users") \
                        .delete() \
                        .eq("cnf_id", selected_cnf_id) \
                        .execute()

                    # Prepare new mappings
                    rows = [
                        {"cnf_id": selected_cnf_id, "user_id": user_map[u]}
                        for u in selected_users
                    ]

                    # Insert new mappings
                    if rows:
                        admin_supabase.table("cnf_users").insert(rows).execute()

                    st.success("✅ CNF–User mapping saved successfully")

                    # Exit edit mode after save
                    st.session_state.cnf_user_edit_mode = False
                    st.rerun()

                except Exception as e:
                    st.error("❌ Failed to save mapping")
                    st.exception(e)

    # =========================
    # PURCHASER MASTER (ADMIN ONLY)
    # =========================
    # =========================
    # PURCHASER MASTER (ADMIN ONLY)
    # =========================
    elif section == "PURCHASER_MASTER":
        st.subheader("🏭 Purchaser Master")

        # ---------- LOAD PURCHASERS (CACHED) ----------
        if "purchaser_master" not in st.session_state:
            purchaser_resp = admin_supabase.table("purchasers") \
                .select("id, name, contact, email, is_active") \
                .order("name") \
                .execute()
            st.session_state.purchaser_master = purchaser_resp.data or []

        # ---------- ADD / EDIT FORM ----------
        editing = st.session_state.purchaser_edit_mode
        editing_id = st.session_state.editing_purchaser_id

        edit_row = None
        if editing and editing_id:
            edit_row = next(
                (p for p in st.session_state.purchaser_master if p["id"] == editing_id),
                None
            )

        with st.form("purchaser_form"):
            purchaser_name = st.text_input(
                "Purchaser Name",
                value=edit_row["name"] if edit_row else ""
            )
            purchaser_contact = st.text_input(
                "Contact",
                value=edit_row["contact"] if edit_row else ""
            )
            purchaser_email = st.text_input(
                "Email ID",
                value=edit_row["email"] if edit_row else ""
            )

            if editing:
                save_btn = st.form_submit_button("💾 Update Purchaser")
            else:
                save_btn = st.form_submit_button("➕ Add Purchaser")

        if save_btn:
            if not purchaser_name.strip():
                st.error("Purchaser name is required")
                st.stop()

            try:
                if editing:
                    admin_supabase.table("purchasers").update({
                        "name": purchaser_name.strip(),
                        "contact": purchaser_contact.strip(),
                        "email": purchaser_email.strip()
                    }).eq("id", editing_id).execute()

                    st.success("✅ Purchaser updated successfully")
                else:
                    admin_supabase.table("purchasers").insert({
                        "name": purchaser_name.strip(),
                        "contact": purchaser_contact.strip(),
                        "email": purchaser_email.strip(),
                        "created_by": resolve_user_id()
                    }).execute()

                    st.success("✅ Purchaser added successfully")

                # Reset state
                st.session_state.purchaser_edit_mode = False
                st.session_state.editing_purchaser_id = None
                st.session_state.pop("purchaser_master", None)
                st.rerun()

            except Exception as e:
                st.error("❌ Failed to save purchaser")
                st.exception(e)

        # ---------- LIST ----------
        st.divider()
        st.subheader("📋 Existing Purchasers")

        if not st.session_state.purchaser_master:
            st.info("No purchasers found")
        else:
            for p in st.session_state.purchaser_master:
                col1, col2, col3, col4, col5 = st.columns([3, 3, 3, 2, 2])

                with col1:
                    st.write(p["name"])

                with col2:
                    st.write(p["contact"] or "-")

                with col3:
                    st.write(p.get("email") or "-")

                with col4:
                    status = "✅ Active" if p["is_active"] else "🚫 Inactive"
                    st.write(status)

                with col5:
                    if st.button("✏️ Edit", key=f"edit_purch_{p['id']}"):
                        st.session_state.purchaser_edit_mode = True
                        st.session_state.editing_purchaser_id = p["id"]
                        st.rerun()

    
    elif section == "ORDERS":
        st.info("🔧 Orders — coming next")

    

    elif section == "PAYMENTS":
        st.subheader("💳 Payments (Phase-2)")

        # =========================
        # PAYMENTS FLOW STATE
        # =========================
        if "pay_flow_stage" not in st.session_state:
            st.session_state.pay_flow_stage = "LINE1"

        if "pay_from_entity_type" not in st.session_state:
            st.session_state.pay_from_entity_type = None
        if "pay_from_entity_id" not in st.session_state:
            st.session_state.pay_from_entity_id = None

        if "pay_to_entity_type" not in st.session_state:
            st.session_state.pay_to_entity_type = None
        if "pay_to_entity_id" not in st.session_state:
            st.session_state.pay_to_entity_id = None

        if "pay_amounts" not in st.session_state:
            st.session_state.pay_amounts = None

        # =========================
        # LINE-1 — PAYMENT DIRECTION
        # =========================
        payment_direction = st.radio(
            "Payment Direction",
            ["Money Received", "Money Paid"],
            horizontal=True
        )

        st.divider()

        # =========================
        # LINE-2 — FROM (ACTUAL ENTITY)
        # =========================
        st.subheader("🔹 From (Actual Entity)")

        from_options = ["Company", "CNF", "User", "Stockist", "Purchaser"]
        from_type = st.selectbox("From Entity Type", from_options)

        from_id = None
        if from_type == "Company":
            st.info("Company selected")
        elif from_type == "CNF":
            m = {c["name"]: c["id"] for c in st.session_state.cnfs_master}
            k = st.selectbox("Select CNF", list(m.keys()))
            from_id = m[k]
        elif from_type == "User":
            m = {u["username"]: u["id"] for u in st.session_state.users_master}
            k = st.selectbox("Select User", list(m.keys()))
            from_id = m[k]
        elif from_type == "Stockist":
            m = {s["name"]: s["id"] for s in st.session_state.stockists_master}
            k = st.selectbox("Select Stockist", list(m.keys()))
            from_id = m[k]
        elif from_type == "Purchaser":
            m = {p["name"]: p["id"] for p in st.session_state.purchasers_master}
            k = st.selectbox("Select Purchaser", list(m.keys()))
            from_id = m[k]

        if st.button("Confirm From"):
            st.session_state.pay_from_entity_type = from_type
            st.session_state.pay_from_entity_id = from_id
            st.rerun()

        if not st.session_state.pay_from_entity_type:
            st.stop()

        st.divider()

        # =========================
        # LINE-3 — TO (ACTUAL ENTITY)
        # =========================
        st.subheader("🔹 To (Actual Entity)")

        to_options = ["Company", "CNF", "User", "Stockist", "Purchaser"]
        to_type = st.selectbox("To Entity Type", to_options)

        to_id = None
        if to_type == "Company":
            st.info("Company selected")
        elif to_type == "CNF":
            m = {c["name"]: c["id"] for c in st.session_state.cnfs_master}
            k = st.selectbox("Select CNF", list(m.keys()))
            to_id = m[k]
        elif to_type == "User":
            m = {u["username"]: u["id"] for u in st.session_state.users_master}
            k = st.selectbox("Select User", list(m.keys()))
            to_id = m[k]
        elif to_type == "Stockist":
            m = {s["name"]: s["id"] for s in st.session_state.stockists_master}
            k = st.selectbox("Select Stockist", list(m.keys()))
            to_id = m[k]
        elif to_type == "Purchaser":
            m = {p["name"]: p["id"] for p in st.session_state.purchasers_master}
            k = st.selectbox("Select Purchaser", list(m.keys()))
            to_id = m[k]

        if st.button("Confirm To"):
            st.session_state.pay_to_entity_type = to_type
            st.session_state.pay_to_entity_id = to_id
            st.rerun()

        if not st.session_state.pay_to_entity_type:
            st.stop()

        st.divider()

        # =========================
        # LINE-4 — PAYMENT META
        # =========================
        pay_date = st.date_input("Payment Date")
        pay_mode = st.selectbox(
            "Payment Mode",
            ["Cash", "Bank", "UPI", "Cheque"]
        )
        pay_ref = st.text_input("Reference No")
        pay_narration = st.text_input("Narration")

        st.divider()

        # =========================
        # LINE-5 — AMOUNT SECTION (LOCKED)
        # =========================
        st.subheader("💰 Amount Details")

        if st.session_state.pay_amounts is None:
            gross = st.number_input("Gross Receipt Amount", min_value=0.0, step=0.01)
            discount = st.number_input("Discount (Optional)", min_value=0.0, step=0.01)
            net = st.number_input("Net Receipt Amount", min_value=0.0, step=0.01)

            if st.button("💾 Save Amounts"):
                st.session_state.pay_amounts = {
                    "gross": gross,
                    "discount": discount,
                    "net": net
                }
                st.rerun()

        else:
            a = st.session_state.pay_amounts
            st.write("Gross:", a["gross"])
            st.write("Discount:", a["discount"])
            st.write("Net:", a["net"])

            if st.button("✏️ Edit / Reset Amount"):
                st.session_state.pay_amounts = None
                st.rerun()

        if not st.session_state.pay_amounts:
            st.stop()

        st.divider()

        # =========================
        # FINAL PREVIEW (NO DB)
        # =========================
        st.subheader("🔍 Final Payment Preview")

        from_disp = resolve_entity_name(
            st.session_state.pay_from_entity_type,
            st.session_state.pay_from_entity_id
        )
        to_disp = resolve_entity_name(
            st.session_state.pay_to_entity_type,
            st.session_state.pay_to_entity_id
        )

        st.write("Direction:", payment_direction)
        st.write("From:", from_disp)
        st.write("To:", to_disp)
        st.write("Date:", pay_date)
        st.write("Mode:", pay_mode)
        st.write("Reference:", pay_ref)
        st.write("Narration:", pay_narration)
        st.write("Net Amount:", st.session_state.pay_amounts["net"])
        st.write("Net Amount:", st.session_state.pay_amounts["net"])

        # =========================
        # FINAL SUBMIT — LEDGER ONLY
        # =========================
        if st.button("✅ Final Submit Payment", type="primary"):
            try:
                user_id = resolve_user_id()
                net_amt = st.session_state.pay_amounts["net"]

                # ---------- DETERMINE DR / CR ----------
                if payment_direction == "Money Received":
                    debit = net_amt
                    credit = 0
                    party_id = (
                        None
                        if st.session_state.pay_from_entity_type == "Company"
                        else st.session_state.pay_from_entity_id
                    )
                else:  # Money Paid
                    debit = 0
                    credit = net_amt
                    party_id = (
                        None
                        if st.session_state.pay_to_entity_type == "Company"
                        else st.session_state.pay_to_entity_id
                    )

                # ---------- CREATE PAYMENT DOCUMENT (HEADER ONLY) ----------
                user_id = resolve_user_id()
                if not user_id:
                    st.error("❌ Invalid user session. Please login again.")
                    st.stop()
                if payment_direction == "Money Received":
                    db_direction = "IN"
                else:
                    db_direction = "OUT"
                doc_resp = admin_supabase.table("ops_documents").insert({
                    "ops_no": f"PAY-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
                    "ops_date": pay_date.isoformat(),
                    "ops_type": ""ADJUSTMENT"",
                    "stock_as": "payment",
                    "direction": db_direction,
                    "narration": pay_narration or "Payment entry",
                    "reference_no": pay_ref,
                    "created_by": user_id
                }).execute()

                payment_ops_id = doc_resp.data[0]["id"]

                # ---------- INSERT FINANCIAL LEDGER ----------
                admin_supabase.table("financial_ledger").insert({
                    "ops_document_id": payment_ops_id,
                    "txn_date": pay_date.isoformat(),
                    "party_id": party_id,
                    "debit": debit,
                    "credit": credit,
                    "closing_balance": 0,
                    "narration": pay_narration or "Payment entry"
                }).execute()

                st.success("✅ Payment saved successfully")


                
            except Exception as e:
                st.error("❌ Failed to save payment")
                st.exception(e)

        st.divider()


        

