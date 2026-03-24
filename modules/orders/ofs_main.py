"""
Order From Stockist Module
Allows field staff to place orders from stockists.

Entry point: run_ofs()
"""

import streamlit as st
import urllib.parse
from datetime import date, datetime

from modules.dcr.dcr_helpers import get_current_user_id
from modules.orders.ofs_database import (
    ofs_get_user_stockists,
    ofs_get_all_products,
    ofs_create_order,
    ofs_load_order,
    ofs_submit_order,
    ofs_delete_order,
    ofs_save_line,
    ofs_delete_line,
    ofs_load_lines,
    ofs_load_archive,
    ofs_format_whatsapp,
)


# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────

def _init():
    defaults = {
        "ofs_screen":    "HOME",    # HOME | NEW | PRODUCTS | REVIEW | DONE | ARCHIVE | VIEW
        "ofs_order_id":  None,
        "ofs_stockist_id":   None,
        "ofs_stockist_name": None,
        "ofs_order_date":    None,
        "ofs_product_seq":   1,
        "ofs_view_id":   None,
        "ofs_delete_confirm": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────────────────────────

def run_ofs():
    _init()
    user_id = get_current_user_id()
    role    = st.session_state.get("role", "user")
    screen  = st.session_state.ofs_screen

    st.title("📦 Order From Stockist")

    if screen == "HOME":
        _home(user_id, role)
    elif screen == "NEW":
        _new_order(user_id, role)
    elif screen == "PRODUCTS":
        _products_screen(user_id, role)
    elif screen == "REVIEW":
        _review_screen(user_id, role)
    elif screen == "DONE":
        _done_screen(user_id, role)
    elif screen == "ARCHIVE":
        _archive_screen(user_id, role)
    elif screen == "VIEW":
        _view_screen(user_id, role)


# ─────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────

def _home(user_id, role):
    st.write("### What would you like to do?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ New Order", type="primary", use_container_width=True):
            # Reset state
            st.session_state.ofs_screen        = "NEW"
            st.session_state.ofs_order_id      = None
            st.session_state.ofs_stockist_id   = None
            st.session_state.ofs_stockist_name = None
            st.session_state.ofs_order_date    = None
            st.session_state.ofs_product_seq   = 1
            st.session_state.ofs_delete_confirm = False
            st.rerun()
    with col2:
        if st.button("📁 View Previous Orders", use_container_width=True):
            st.session_state.ofs_screen = "ARCHIVE"
            st.rerun()


# ─────────────────────────────────────────────────────────────
# STEP 1 — NEW ORDER HEADER
# ─────────────────────────────────────────────────────────────

def _new_order(user_id, role):
    st.write("### Step 1 — Order Details")

    if st.button("⬅️ Back to Home"):
        st.session_state.ofs_screen = "HOME"
        st.rerun()

    st.write("---")

    # Stockist selection
    stockists = ofs_get_user_stockists(user_id)
    if not stockists:
        st.error("❌ No stockists assigned to your account. Please contact admin.")
        return

    sel_stockist = st.selectbox(
        "Select Stockist *",
        options=[None] + [s["id"] for s in stockists],
        format_func=lambda x: "— Select a Stockist —" if x is None
                               else next(s["name"] for s in stockists if s["id"] == x),
        key="ofs_new_stockist"
    )

    # Date
    order_date = st.date_input(
        "Order Date *",
        value=date.today(),
        max_value=date.today(),
        key="ofs_new_date"
    )

    st.write("---")

    if st.button("Next ➡️ Add Products", type="primary", use_container_width=True):
        if sel_stockist is None:
            st.error("❌ Please select a stockist.")
            return

        stockist_name = next(s["name"] for s in stockists if s["id"] == sel_stockist)

        # Create order in DB
        order_id = ofs_create_order(user_id, sel_stockist, order_date)
        if not order_id:
            st.error("❌ Failed to create order. Please try again.")
            return

        st.session_state.ofs_order_id      = order_id
        st.session_state.ofs_stockist_id   = sel_stockist
        st.session_state.ofs_stockist_name = stockist_name
        st.session_state.ofs_order_date    = str(order_date)
        st.session_state.ofs_product_seq   = 1
        st.session_state.ofs_screen        = "PRODUCTS"
        st.rerun()


# ─────────────────────────────────────────────────────────────
# STEP 2 — ADD PRODUCTS
# ─────────────────────────────────────────────────────────────

def _products_screen(user_id, role):
    order_id = st.session_state.ofs_order_id

    if not order_id:
        st.error("❌ No order found. Please start again.")
        st.session_state.ofs_screen = "HOME"
        st.rerun()
        return

    order    = ofs_load_order(order_id)
    lines    = ofs_load_lines(order_id)
    products = ofs_get_all_products()

    # Header info
    st.info(
        f"📦 **{order.get('order_no', '...')}** | "
        f"Stockist: **{order.get('stockist_name', '...')}** | "
        f"Date: {order.get('order_date', '...')}"
    )

    # ── Existing lines ────────────────────────────────────────
    if lines:
        st.write(f"**✅ {len(lines)} product(s) added:**")
        for line in lines:
            disc_label = "MRP" if line.get("discount_type") == "ON_MRP" else "Invoice"
            with st.expander(
                f"{line['seq_no']}. {line['product_name']} | "
                f"Sale: {line['sale_qty']} | Free: {line['free_qty']} | "
                f"Disc: {line.get('discount', 0)}% on {disc_label}"
            ):
                col_edit, col_del = st.columns([3, 1])
                with col_edit:
                    e_sale = st.number_input(
                        "Sale Qty", value=int(line["sale_qty"]),
                        min_value=0, step=1, key=f"e_sale_{line['id']}"
                    )
                    e_free = st.number_input(
                        "Free Qty", value=int(line["free_qty"]),
                        min_value=0, step=1, key=f"e_free_{line['id']}"
                    )
                    e_disc = st.number_input(
                        "Discount %", value=float(line.get("discount", 0)),
                        min_value=0.0, max_value=100.0, step=0.5,
                        key=f"e_disc_{line['id']}"
                    )
                    e_dtype = st.radio(
                        "Discount on",
                        options=["ON_MRP", "ON_INVOICE"],
                        format_func=lambda x: "MRP" if x == "ON_MRP" else "Invoice",
                        index=0 if line.get("discount_type") == "ON_MRP" else 1,
                        horizontal=True,
                        key=f"e_dtype_{line['id']}"
                    )
                    if st.button("💾 Update", key=f"upd_{line['id']}"):
                        ofs_save_line(
                            order_id, line["product_id"], line["product_name"],
                            line["seq_no"], e_sale, e_free, e_disc, e_dtype
                        )
                        st.success("Updated!")
                        st.rerun()
                with col_del:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Remove", key=f"del_{line['id']}"):
                        ofs_delete_line(line["id"])
                        st.rerun()

    st.write("---")

    # ── Add new product form ──────────────────────────────────
    st.write("#### ➕ Add Product")

    # Already added product ids
    added_ids = [l["product_id"] for l in lines]
    available = [p for p in products if p["id"] not in added_ids]

    if not available:
        st.info("✅ All products have been added.")
    else:
        with st.form("ofs_add_product_form", clear_on_submit=True):
            sel_product = st.selectbox(
                "Product *",
                options=[None] + [p["id"] for p in available],
                format_func=lambda x: "— Select a product —" if x is None
                                       else next(p["name"] for p in available if p["id"] == x),
                key="ofs_prod_select"
            )

            col1, col2 = st.columns(2)
            with col1:
                sale_qty = st.number_input("Sale Quantity *", min_value=0, step=1, value=0)
            with col2:
                free_qty = st.number_input("Free Quantity", min_value=0, step=1, value=0)

            col3, col4 = st.columns(2)
            with col3:
                discount = st.number_input(
                    "Discount %", min_value=0.0, max_value=100.0,
                    step=0.5, value=0.0
                )
            with col4:
                discount_type = st.radio(
                    "Discount on",
                    options=["ON_MRP", "ON_INVOICE"],
                    format_func=lambda x: "MRP" if x == "ON_MRP" else "Invoice",
                    horizontal=True
                )

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                save_next = st.form_submit_button("💾 Save & Next Product", type="primary")
            with col_b:
                end_btn   = st.form_submit_button("🏁 End — Go to Review")
            with col_c:
                prev_btn  = st.form_submit_button("⬅️ Previous")

        if save_next:
            if sel_product is None:
                st.error("❌ Please select a product.")
            elif sale_qty <= 0 and free_qty <= 0:
                st.error("❌ Please enter at least a sale qty or free qty.")
            else:
                product_name = next(p["name"] for p in available if p["id"] == sel_product)
                seq = st.session_state.ofs_product_seq
                ofs_save_line(order_id, sel_product, product_name,
                              seq, sale_qty, free_qty, discount, discount_type)
                st.session_state.ofs_product_seq = seq + 1
                st.success(f"✅ {product_name} added!")
                st.rerun()

        if end_btn:
            if not lines:
                st.error("❌ Please add at least one product before reviewing.")
            else:
                st.session_state.ofs_screen = "REVIEW"
                st.rerun()

        if prev_btn:
            st.session_state.ofs_screen = "NEW"
            st.rerun()

    # ── Bottom navigation ─────────────────────────────────────
    st.write("---")
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("⬅️ Back to Order Details"):
            st.session_state.ofs_screen = "NEW"
            st.rerun()
    with col_nav2:
        if lines:
            if st.button("➡️ Review & Submit", type="primary", use_container_width=True):
                st.session_state.ofs_screen = "REVIEW"
                st.rerun()


# ─────────────────────────────────────────────────────────────
# STEP 3 — REVIEW
# ─────────────────────────────────────────────────────────────

def _review_screen(user_id, role):
    order_id = st.session_state.ofs_order_id
    order    = ofs_load_order(order_id)
    lines    = ofs_load_lines(order_id)

    st.write("### 📋 Order Review")

    if st.button("⬅️ Back to Products"):
        st.session_state.ofs_screen = "PRODUCTS"
        st.rerun()

    st.write("---")

    # Order summary
    st.write(f"**Order No:** {order.get('order_no', '...')}")
    st.write(f"**Date:** {order.get('order_date', '...')}")
    st.write(f"**Stockist:** {order.get('stockist_name', '...')}")
    st.write(f"**Total Products:** {len(lines)}")

    st.write("---")

    if not lines:
        st.warning("No products added. Please go back and add products.")
        return

    # Lines table
    for line in lines:
        disc_label = "on MRP" if line.get("discount_type") == "ON_MRP" else "on Invoice"
        st.write(
            f"**{line['seq_no']}. {line['product_name']}** — "
            f"Sale: {line['sale_qty']} | Free: {line['free_qty']} | "
            f"Disc: {line.get('discount', 0)}% {disc_label}"
        )

    st.write("---")

    # Final Submit
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Final Submit", type="primary", use_container_width=True):
            ofs_submit_order(order_id, user_id)
            st.session_state.ofs_screen = "DONE"
            st.rerun()
    with col2:
        if st.button("❌ Cancel & Delete Order", use_container_width=True):
            if st.session_state.ofs_delete_confirm:
                ofs_delete_order(order_id, user_id)
                st.session_state.ofs_screen        = "HOME"
                st.session_state.ofs_order_id      = None
                st.session_state.ofs_delete_confirm = False
                st.success("Order deleted.")
                st.rerun()
            else:
                st.session_state.ofs_delete_confirm = True
                st.warning("⚠️ Click again to confirm deletion.")
                st.rerun()


# ─────────────────────────────────────────────────────────────
# STEP 4 — DONE (post submit)
# ─────────────────────────────────────────────────────────────

def _done_screen(user_id, role):
    st.success("✅ Order submitted successfully!")

    order_id = st.session_state.ofs_order_id
    order    = ofs_load_order(order_id)
    lines    = ofs_load_lines(order_id)

    st.write("---")
    st.write(f"**Order No:** {order.get('order_no', '...')}")
    st.write(f"**Stockist:** {order.get('stockist_name', '...')}")
    st.write(f"**Date:** {order.get('order_date', '...')}")
    st.write(f"**Total Products:** {len(lines)}")

    st.write("---")
    st.write("**What would you like to do next?**")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📱 Share on WhatsApp", use_container_width=True):
            msg = ofs_format_whatsapp(order, lines)
            encoded = urllib.parse.quote(msg)
            wa_url  = f"https://wa.me/?text={encoded}"
            st.link_button("📱 Open WhatsApp", url=wa_url, use_container_width=True)

    with col2:
        if st.button("👁️ Preview Order", use_container_width=True):
            st.session_state.ofs_view_id = order_id
            st.session_state.ofs_screen  = "VIEW"
            st.rerun()

    with col3:
        if st.button("🗑️ Delete This Order", use_container_width=True):
            if st.session_state.get("ofs_done_del_confirm"):
                ofs_delete_order(order_id, user_id)
                st.session_state.ofs_screen        = "HOME"
                st.session_state.ofs_order_id      = None
                st.session_state.ofs_done_del_confirm = False
                st.success("Order deleted.")
                st.rerun()
            else:
                st.session_state.ofs_done_del_confirm = True
                st.warning("⚠️ Click again to confirm deletion.")
                st.rerun()

    st.write("")
    if st.button("➕ New Order", type="primary", use_container_width=True):
        st.session_state.ofs_screen        = "HOME"
        st.session_state.ofs_order_id      = None
        st.session_state.ofs_stockist_id   = None
        st.session_state.ofs_stockist_name = None
        st.session_state.ofs_order_date    = None
        st.session_state.ofs_product_seq   = 1
        st.session_state.ofs_delete_confirm = False
        st.rerun()

    if st.button("🏠 Back to Home"):
        st.session_state.ofs_screen = "HOME"
        st.rerun()


# ─────────────────────────────────────────────────────────────
# ARCHIVE — Previous Orders
# ─────────────────────────────────────────────────────────────

def _archive_screen(user_id, role):
    st.write("### 📁 Previous Orders")

    if st.button("⬅️ Back to Home"):
        st.session_state.ofs_screen = "HOME"
        st.rerun()

    st.write("---")

    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        stockists = ofs_get_user_stockists(user_id)
        stockist_opts = {None: "— All Stockists —"}
        for s in stockists:
            stockist_opts[s["id"]] = s["name"]
        stockist_filter = st.selectbox(
            "Filter by Stockist",
            options=list(stockist_opts.keys()),
            format_func=lambda x: stockist_opts[x],
            key="ofs_arc_stockist"
        )
    with col2:
        status_filter = st.selectbox(
            "Status",
            options=["ALL", "draft", "submitted"],
            format_func=lambda x: "All" if x == "ALL" else x.capitalize(),
            key="ofs_arc_status"
        )
    with col3:
        st.write("")
        if st.button("🔄 Refresh"):
            st.rerun()

    orders = ofs_load_archive(user_id, role,
                               stockist_filter=stockist_filter,
                               status_filter=status_filter)

    if not orders:
        st.info("No orders found.")
        return

    st.write(f"**{len(orders)} order(s) found**")
    st.write("---")

    for order in orders:
        status_icon = "✅" if order["status"] == "submitted" else "📝"
        label = (
            f"{status_icon} {order.get('order_no', 'N/A')} | "
            f"{order['stockist_name']} | "
            f"{order.get('order_date', 'N/A')}"
        )
        # Admin also sees username
        if role == "admin":
            label += f" | 👤 {order.get('username', 'Unknown')}"

        with st.expander(label):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.write(f"**Order No:** {order.get('order_no', 'N/A')}")
                st.write(f"**Date:** {order.get('order_date', 'N/A')}")
                st.write(f"**Status:** {order['status'].capitalize()}")
            with col_b:
                st.write(f"**Stockist:** {order['stockist_name']}")
                if role == "admin":
                    st.write(f"**User:** {order.get('username', 'Unknown')}")
            with col_c:
                if st.button("👁️ View", key=f"arc_view_{order['id']}"):
                    st.session_state.ofs_view_id = order["id"]
                    st.session_state.ofs_screen  = "VIEW"
                    st.rerun()
                if order["status"] == "submitted":
                    order_for_wa = order
                    lines_for_wa = ofs_load_lines(order["id"])
                    msg     = ofs_format_whatsapp(order_for_wa, lines_for_wa)
                    encoded = urllib.parse.quote(msg)
                    st.link_button(
                        "📱 WhatsApp",
                        url=f"https://wa.me/?text={encoded}"
                    )


# ─────────────────────────────────────────────────────────────
# VIEW SINGLE ORDER
# ─────────────────────────────────────────────────────────────

def _view_screen(user_id, role):
    view_id = st.session_state.ofs_view_id

    if not view_id:
        st.session_state.ofs_screen = "ARCHIVE"
        st.rerun()
        return

    order = ofs_load_order(view_id)
    lines = ofs_load_lines(view_id)

    if st.button("⬅️ Back"):
        st.session_state.ofs_screen = "ARCHIVE"
        st.rerun()

    st.write("---")
    st.write(f"## 📦 {order.get('order_no', 'N/A')}")
    st.write(f"**Stockist:** {order.get('stockist_name', 'N/A')}")
    st.write(f"**Date:** {order.get('order_date', 'N/A')}")
    st.write(f"**Status:** {order.get('status', 'N/A').capitalize()}")
    st.write(f"**Submitted at:** {order.get('submitted_at', 'N/A')}")
    st.write("---")

    if not lines:
        st.info("No products in this order.")
    else:
        st.write(f"**Products ({len(lines)}):**")
        for line in lines:
            disc_label = "on MRP" if line.get("discount_type") == "ON_MRP" else "on Invoice"
            st.write(
                f"**{line['seq_no']}. {line['product_name']}**  —  "
                f"Sale Qty: {line['sale_qty']}  |  "
                f"Free Qty: {line['free_qty']}  |  "
                f"Discount: {line.get('discount', 0)}% {disc_label}"
            )

        # Totals
        st.write("---")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Products", len(lines))
        with col2:
            st.metric("Total Sale Qty", sum(l["sale_qty"] for l in lines))

    # WhatsApp
    st.write("---")
    msg     = ofs_format_whatsapp(order, lines)
    encoded = urllib.parse.quote(msg)
    st.link_button(
        "📱 Share on WhatsApp",
        url=f"https://wa.me/?text={encoded}",
        use_container_width=True
    )

    # Delete (admin or own draft)
    if role == "admin" or order.get("status") == "draft":
        st.write("---")
        if st.button("🗑️ Delete Order"):
            if st.session_state.get("ofs_view_del_confirm"):
                ofs_delete_order(view_id, user_id)
                st.session_state.ofs_screen           = "ARCHIVE"
                st.session_state.ofs_view_id          = None
                st.session_state.ofs_view_del_confirm = False
                st.success("Order deleted.")
                st.rerun()
            else:
                st.session_state.ofs_view_del_confirm = True
                st.warning("⚠️ Click again to confirm.")
                st.rerun()
