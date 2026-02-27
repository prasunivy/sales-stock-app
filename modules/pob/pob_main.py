"""
POB Main Module — Standalone top-level module
Handles POB / Statement / Credit Note creation, review, submit and archive.
Accessed via the main sidebar, NOT inside DCR.
"""

import streamlit as st
import urllib.parse
from datetime import date

from modules.dcr.dcr_helpers import get_current_user_id
from modules.pob.pob_database import (
    pob_get_user_chemists,
    pob_get_user_stockists,
    pob_get_all_products,
    pob_create_document,
    pob_load_document,
    pob_submit_document,
    pob_save_line,
    pob_update_line,
    pob_delete_line,
    pob_load_lines,
    pob_load_archive,
    pob_approve,
    pob_reject,
    pob_calculate_line,
    pob_format_whatsapp,
    pob_generate_pdf,
)

DOC_LABELS = {
    "POB":       "📋 POB",
    "STATEMENT": "📄 Statement",
    "CREDIT_NOTE": "🔄 Credit Note",
}

STATUS_ICON = {
    "pending":  "🕐",
    "approved": "✅",
    "rejected": "❌",
}


# ─────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────

def _init():
    defaults = {
        "pob_screen":       "HOME",    # HOME | NEW | ARCHIVE | VIEW
        "pob_step":         "PARTY",   # PARTY | DOCTYPE | HEADER | PRODUCTS | REVIEW | DONE
        "pob_doc_id":       None,
        "pob_doc_type":     None,
        "pob_party_type":   None,
        "pob_party_id":     None,
        "pob_party_name":   None,
        "pob_seq":          1,
        "pob_calc":         {},
        "pob_edit_line":    None,
        "pob_view_id":      None,
        "pob_arc_status":   "ALL",
        "pob_arc_type":     "ALL",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────

def run_pob():
    _init()
    user_id = get_current_user_id()
    role    = st.session_state.get("role", "user")
    screen  = st.session_state.pob_screen

    st.title("📋 POB / Statement / Credit Note")

    if screen == "HOME":
        _home(user_id, role)
    elif screen == "NEW":
        _new_flow(user_id, role)
    elif screen == "ARCHIVE":
        _archive(user_id, role)
    elif screen == "VIEW":
        _view_doc(user_id, role)


# ─────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────

def _home(user_id, role):
    st.write("### What would you like to do?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Create New Document", type="primary",
                     use_container_width=True):
            # Reset new-doc state
            st.session_state.pob_step      = "PARTY"
            st.session_state.pob_doc_id    = None
            st.session_state.pob_doc_type  = None
            st.session_state.pob_party_type = None
            st.session_state.pob_party_id  = None
            st.session_state.pob_party_name = None
            st.session_state.pob_seq       = 1
            st.session_state.pob_calc      = {}
            st.session_state.pob_edit_line = None
            st.session_state.pob_screen    = "NEW"
            st.rerun()
    with col2:
        if st.button("📁 Archive", use_container_width=True):
            st.session_state.pob_screen = "ARCHIVE"
            st.rerun()


# ─────────────────────────────────────────────────────────────
# NEW DOCUMENT FLOW
# ─────────────────────────────────────────────────────────────

def _new_flow(user_id, role):
    step = st.session_state.pob_step
    if step == "PARTY":
        _step_party(user_id)
    elif step == "DOCTYPE":
        _step_doctype()
    elif step == "HEADER":
        _step_header(user_id)
    elif step == "PRODUCTS":
        _step_products(user_id)
    elif step == "REVIEW":
        _step_review(user_id, role)
    elif step == "DONE":
        _step_done()


# ── STEP 1: SELECT PARTY ─────────────────────────────────────

def _step_party(user_id):
    st.write("### Step 1 — Select Party")

    chemists  = pob_get_user_chemists(user_id)
    stockists = pob_get_user_stockists(user_id)

    ptype = st.radio("Party Type", ["Chemist", "Stockist"], horizontal=True,
                     key="pob_ptype_radio")

    if ptype == "Chemist":
        if not chemists:
            st.warning("No chemists found in your territories.")
            _back_home()
            return
        sel = st.selectbox(
            "Select Chemist", [c["id"] for c in chemists],
            format_func=lambda x: next(
                f"{c['name']}  ({c.get('shop_name') or '—'})"
                for c in chemists if c["id"] == x),
            key="pob_chemist_sel"
        )
        name  = next(c["name"] for c in chemists if c["id"] == sel)
        ptype_val = "CHEMIST"
    else:
        if not stockists:
            st.warning("No stockists linked to your account.")
            _back_home()
            return
        sel = st.selectbox(
            "Select Stockist", [s["id"] for s in stockists],
            format_func=lambda x: next(s["name"] for s in stockists if s["id"] == x),
            key="pob_stockist_sel"
        )
        name  = next(s["name"] for s in stockists if s["id"] == sel)
        ptype_val = "STOCKIST"

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Next ➡️", type="primary", use_container_width=True,
                     key="pob_party_next"):
            st.session_state.pob_party_type = ptype_val
            st.session_state.pob_party_id   = sel
            st.session_state.pob_party_name = name
            st.session_state.pob_step       = "DOCTYPE"
            st.rerun()
    with col2:
        _back_home()


# ── STEP 2: SELECT DOCUMENT TYPE ─────────────────────────────

def _step_doctype():
    st.write("### Step 2 — Select Document Type")
    st.info(f"Party: **{st.session_state.pob_party_name}**")

    chosen = None
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📋 POB", use_container_width=True,
                     type="primary", key="pob_type_pob"):
            chosen = "POB"
    with c2:
        if st.button("📄 Statement", use_container_width=True,
                     key="pob_type_stmt"):
            chosen = "STATEMENT"
    with c3:
        if st.button("🔄 Credit Note", use_container_width=True,
                     key="pob_type_crnt"):
            chosen = "CREDIT_NOTE"

    if chosen:
        st.session_state.pob_doc_type = chosen
        st.session_state.pob_step     = "HEADER"
        st.rerun()

    st.write("")
    if st.button("⬅️ Back", key="pob_doctype_back"):
        st.session_state.pob_step = "PARTY"
        st.rerun()


# ── STEP 3: DATE (HEADER) ─────────────────────────────────────

def _step_header(user_id):
    label = DOC_LABELS.get(st.session_state.pob_doc_type, "Document")
    st.write(f"### Step 3 — {label}")
    st.info(f"Party: **{st.session_state.pob_party_name}**")

    doc_date = st.date_input("Document Date", value=date.today(),
                              key="pob_doc_date")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Next ➡️", type="primary", use_container_width=True,
                     key="pob_header_next"):
            doc_id = pob_create_document(
                doc_type   = st.session_state.pob_doc_type,
                doc_date   = doc_date,
                party_type = st.session_state.pob_party_type,
                party_id   = st.session_state.pob_party_id,
                party_name = st.session_state.pob_party_name,
                user_id    = user_id,
            )
            if doc_id:
                st.session_state.pob_doc_id = doc_id
                st.session_state.pob_seq    = 1
                st.session_state.pob_calc   = {}
                st.session_state.pob_step   = "PRODUCTS"
                st.rerun()
    with col2:
        if st.button("⬅️ Back", use_container_width=True, key="pob_header_back"):
            st.session_state.pob_step = "DOCTYPE"
            st.rerun()


# ── STEP 4: PRODUCTS ─────────────────────────────────────────

def _step_products(user_id):
    doc_id   = st.session_state.pob_doc_id
    lines    = pob_load_lines(doc_id)
    products = pob_get_all_products()
    editing  = st.session_state.pob_edit_line
    calc     = st.session_state.pob_calc

    label = DOC_LABELS.get(st.session_state.pob_doc_type, "Document")
    st.write(f"### {label} — Add Products")
    st.info(f"Party: **{st.session_state.pob_party_name}** | "
            f"Products added: **{len(lines)}**")

    # Already-added lines
    if lines:
        st.write("**Products added so far:**")
        for ln in lines:
            ca, cb = st.columns([5, 1])
            with ca:
                st.write(f"• **{ln['product_name']}**  |  "
                         f"Qty: {ln['sale_qty']} + {ln['free_qty']} free  |  "
                         f"Net: ₹{float(ln['net_rate']):.2f}")
            with cb:
                if st.button("✏️", key=f"prod_edit_{ln['id']}"):
                    st.session_state.pob_edit_line = ln["id"]
                    # Pre-seed calc so results show without recalculating
                    st.session_state.pob_calc = {
                        "mrp_excl_tax": ln["mrp_excl_tax"],
                        "retail_price": ln["retail_price"],
                        "sales_price":  ln["sales_price"],
                        "tax_amount":   ln["tax_amount"],
                        "gross_rate":   ln["gross_rate"],
                        "net_rate":     ln["net_rate"],
                    }
                    st.rerun()
        st.write("---")

    # Find prefill values if editing
    prefill = {}
    if editing:
        prefill = next((l for l in lines if l["id"] == editing), {})

    heading = "#### ✏️ Edit Product" if editing else f"#### ➕ Product {len(lines)+1}"
    st.write(heading)

    if not products:
        st.error("No products found in the database.")
        return

    # Build dropdown options
    added_ids = [l["product_id"] for l in lines if l["id"] != editing]
    available = [p for p in products if p["id"] not in added_ids]
    prod_list = products if editing else available

    if not prod_list and not editing:
        st.info("All products have been added.")
        if lines:
            if st.button("✅ Go to Review", type="primary"):
                st.session_state.pob_step = "REVIEW"
                st.rerun()
        return

    # Default index for editing
    def_idx = 0
    if prefill.get("product_id"):
        ids = [p["id"] for p in prod_list]
        if prefill["product_id"] in ids:
            def_idx = ids.index(prefill["product_id"])

    sel_product = st.selectbox(
        "Select Product *",
        [p["id"] for p in prod_list],
        format_func=lambda x: next(p["name"] for p in prod_list if p["id"] == x),
        index=def_idx,
        key=f"pob_prod_{editing or 'new'}"
    )

    col1, col2 = st.columns(2)
    with col1:
        sale_qty = st.number_input("(a) Sales Qty", min_value=0.0, step=1.0,
            value=float(prefill.get("sale_qty", 0)),
            key=f"pob_sq_{editing or 'new'}")
        mrp_incl = st.number_input("(c) MRP incl. Tax ₹", min_value=0.0, step=0.5,
            value=float(prefill.get("mrp_incl_tax", 0)),
            key=f"pob_mrp_{editing or 'new'}")
        discount = st.number_input("(e) Discount %", min_value=0.0, max_value=100.0, step=0.5,
            value=float(prefill.get("discount", 0)),
            key=f"pob_disc_{editing or 'new'}")
    with col2:
        free_qty = st.number_input("(b) Free Qty", min_value=0.0, step=1.0,
            value=float(prefill.get("free_qty", 0)),
            key=f"pob_fq_{editing or 'new'}")
        tax_rate = st.number_input("(d) Tax Rate %", min_value=0.0, max_value=100.0, step=1.0,
            value=float(prefill.get("tax_rate", 0)),
            key=f"pob_tax_{editing or 'new'}")

    # Calculate button
    if st.button("🔢 Calculate", type="primary", key=f"pob_calc_btn_{editing or 'new'}"):
        if mrp_incl <= 0:
            st.error("Please enter MRP greater than 0")
        elif sale_qty <= 0:
            st.error("Please enter sales quantity greater than 0")
        else:
            st.session_state.pob_calc = pob_calculate_line(
                sale_qty, free_qty, mrp_incl, tax_rate, discount)
            calc = st.session_state.pob_calc
            st.rerun()

    # Show calculated values and action buttons only after calculate is clicked
    if calc:
        st.write("---")
        st.write("**📊 Calculated Values:**")

        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("(f) MRP excl. Tax",  f"₹{calc['mrp_excl_tax']:.4f}")
            st.metric("(i) Sales Price",     f"₹{calc['sales_price']:.4f}")
            st.metric("(k) Gross Rate/unit", f"₹{calc['gross_rate']:.4f}")
        with r2:
            st.metric("(g) Retail Price",    f"₹{calc['retail_price']:.4f}")
            st.metric("(j) Tax Amount",      f"₹{calc['tax_amount']:.4f}")
            st.metric("(l) Net Rate (total)","₹{:.4f}".format(calc['net_rate']))
        with r3:
            st.metric("Sale Qty",  int(sale_qty))
            st.metric("Free Qty",  int(free_qty))

        st.write("---")
        prod_name = next(p["name"] for p in prod_list if p["id"] == sel_product)

        def _save_current(go_to):
            if editing:
                pob_update_line(editing, sale_qty, free_qty, mrp_incl, tax_rate,
                                discount, **calc)
                st.session_state.pob_edit_line = None
            else:
                pob_save_line(doc_id, sel_product, prod_name,
                              st.session_state.pob_seq,
                              sale_qty, free_qty, mrp_incl, tax_rate,
                              discount, **calc)
                st.session_state.pob_seq += 1
            st.session_state.pob_calc = {}
            st.session_state.pob_step = go_to
            st.rerun()

        cs, ce, cc = st.columns(3)
        with cs:
            if st.button("💾 Save & Next Product", type="primary",
                         use_container_width=True,
                         key=f"pob_save_next_{editing or 'new'}"):
                _save_current("PRODUCTS")
        with ce:
            if st.button("✅ End Products", use_container_width=True,
                         key=f"pob_end_{editing or 'new'}"):
                _save_current("REVIEW")
        with cc:
            if editing:
                if st.button("❌ Cancel Edit", use_container_width=True,
                             key="pob_cancel_edit"):
                    st.session_state.pob_edit_line = None
                    st.session_state.pob_calc = {}
                    st.rerun()
    else:
        # No calculation yet — allow ending if lines already exist
        if lines and not editing:
            st.write("")
            if st.button("✅ End Products (no more to add)",
                         key="pob_end_nocalc"):
                st.session_state.pob_step = "REVIEW"
                st.rerun()


# ── STEP 5: REVIEW ───────────────────────────────────────────

def _step_review(user_id, role):
    doc_id = st.session_state.pob_doc_id
    doc    = pob_load_document(doc_id)
    lines  = pob_load_lines(doc_id)
    label  = DOC_LABELS.get(st.session_state.pob_doc_type, "Document")

    st.write(f"### Review — {label}")

    if not doc:
        st.error("Document not found.")
        return
    if not lines:
        st.warning("No products added. Please go back and add at least one product.")
        if st.button("⬅️ Back to Products"):
            st.session_state.pob_step = "PRODUCTS"
            st.rerun()
        return

    # Doc header
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"**Doc No:** {doc['pob_no']}")
        st.write(f"**Date:** {doc['doc_date']}")
    with c2:
        st.write(f"**Party:** {doc['party_name']}")
        st.write(f"**Type:** {doc['party_type'].capitalize()}")
    with c3:
        st.write(f"**Status:** 🕐 Pending")

    st.write("---")

    total = 0.0
    for idx, ln in enumerate(lines, 1):
        ca, cb = st.columns([6, 1])
        with ca:
            st.write(f"**{idx}. {ln['product_name']}**")
            r1, r2, r3, r4, r5 = st.columns(5)
            with r1:
                st.write(f"Sale: **{ln['sale_qty']}**")
                st.write(f"Free: **{ln['free_qty']}**")
            with r2:
                st.write(f"MRP: **₹{float(ln['mrp_incl_tax']):.2f}**")
                st.write(f"Tax: **{ln['tax_rate']}%**")
            with r3:
                st.write(f"Disc: **{ln['discount']}%**")
                st.write(f"S.Price: **₹{float(ln['sales_price']):.4f}**")
            with r4:
                st.write(f"Tax Amt: **₹{float(ln['tax_amount']):.4f}**")
                st.write(f"Gross: **₹{float(ln['gross_rate']):.4f}**")
            with r5:
                st.write(f"**Net: ₹{float(ln['net_rate']):.2f}**")
        with cb:
            if st.button("✏️", key=f"rev_edit_{ln['id']}"):
                st.session_state.pob_edit_line = ln["id"]
                st.session_state.pob_calc = {
                    k: ln[k] for k in
                    ["mrp_excl_tax","retail_price","sales_price",
                     "tax_amount","gross_rate","net_rate"]
                }
                st.session_state.pob_step = "PRODUCTS"
                st.rerun()
            if st.button("🗑️", key=f"rev_del_{ln['id']}"):
                pob_delete_line(ln["id"])
                st.rerun()
        total += float(ln["net_rate"])
        st.write("---")

    st.success(f"### 💰 Grand Total: ₹{total:.2f}")

    cs, cb2 = st.columns(2)
    with cs:
        if st.button("✅ Final Submit", type="primary",
                     use_container_width=True, key="pob_final_submit"):
            pob_submit_document(doc_id)
            st.session_state.pob_step = "DONE"
            st.rerun()
    with cb2:
        if st.button("⬅️ Back to Products", use_container_width=True,
                     key="pob_rev_back"):
            st.session_state.pob_step = "PRODUCTS"
            st.rerun()


# ── STEP 6: DONE ─────────────────────────────────────────────

def _step_done():
    doc_id = st.session_state.pob_doc_id
    doc    = pob_load_document(doc_id)
    lines  = pob_load_lines(doc_id)

    if not doc:
        st.error("Document not found.")
        return

    label = DOC_LABELS.get(doc["doc_type"], "Document")
    st.success(f"✅ {label} **{doc['pob_no']}** submitted! Status: 🕐 Pending")
    st.write(f"Party: **{doc['party_name']}** | Date: **{doc['doc_date']}**")

    total = sum(float(l["net_rate"]) for l in lines)
    st.write(f"**{len(lines)} product(s) | Total: ₹{total:.2f}**")
    st.write("---")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        msg    = pob_format_whatsapp(doc, lines)
        wa_url = "https://wa.me/?text=" + urllib.parse.quote(msg)
        st.link_button("📱 WhatsApp", wa_url, use_container_width=True)
    with c2:
        pdf_bytes = pob_generate_pdf(doc, lines)
        if pdf_bytes:
            st.download_button("📄 PDF", data=pdf_bytes,
                               file_name=f"{doc['pob_no']}.pdf",
                               mime="application/pdf",
                               use_container_width=True)
        else:
            st.caption("PDF: install reportlab")
    with c3:
        if st.button("➡️ Next Document", use_container_width=True,
                     key="pob_done_next"):
            # Reset for fresh document — any party
            for k in ["pob_doc_id","pob_doc_type","pob_party_type",
                      "pob_party_id","pob_party_name","pob_calc","pob_edit_line"]:
                st.session_state[k] = None
            st.session_state.pob_seq  = 1
            st.session_state.pob_step = "PARTY"
            st.rerun()
    with c4:
        if st.button("🏠 Home", use_container_width=True, key="pob_done_home"):
            st.session_state.pob_screen = "HOME"
            st.rerun()


# ─────────────────────────────────────────────────────────────
# ARCHIVE
# ─────────────────────────────────────────────────────────────

def _archive(user_id, role):
    st.write("### 📁 Archive")

    # Filters
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        status_f = st.selectbox("Status",
            ["ALL","PENDING","APPROVED","REJECTED"],
            index=["ALL","PENDING","APPROVED","REJECTED"].index(
                st.session_state.pob_arc_status),
            key="pob_arc_s_sel")
        st.session_state.pob_arc_status = status_f
    with fc2:
        type_f = st.selectbox("Doc Type",
            ["ALL","POB","STATEMENT","CREDIT_NOTE"],
            key="pob_arc_t_sel")
        st.session_state.pob_arc_type = type_f
    with fc3:
        if st.button("🔄 Refresh", key="pob_arc_refresh"):
            st.rerun()

    docs = pob_load_archive(user_id, role, status_f, type_f)
    st.write(f"**{len(docs)} document(s)**")
    st.write("---")

    if not docs:
        st.info("No documents found.")
    else:
        for doc in docs:
            icon     = STATUS_ICON.get(doc["status"], "❓")
            username = (doc.get("users") or {}).get("username", "—")

            with st.expander(
                f"{icon} {doc['pob_no']}  |  {doc['party_name']}  |  "
                f"{doc['doc_date']}  |  by {username}"
            ):
                d1, d2, d3 = st.columns([2, 2, 2])
                with d1:
                    st.write(f"**Type:** {DOC_LABELS.get(doc['doc_type'], doc['doc_type'])}")
                    st.write(f"**Party:** {doc['party_name']}")
                    st.write(f"**Date:** {doc['doc_date']}")
                with d2:
                    st.write(f"**Status:** {icon} {doc['status'].upper()}")
                    st.write(f"**By:** {username}")
                    if doc.get("approval_comment"):
                        st.write(f"**Comment:** {doc['approval_comment']}")
                with d3:
                    if st.button("👁️ View", key=f"arc_view_{doc['id']}",
                                 use_container_width=True):
                        st.session_state.pob_view_id = doc["id"]
                        st.session_state.pob_screen  = "VIEW"
                        st.rerun()

                    # Admin approve / reject on pending docs
                    if role == "admin" and doc["status"] == "pending":
                        comment = st.text_input("Comment",
                                                key=f"arc_comment_{doc['id']}")
                        ap, rj = st.columns(2)
                        with ap:
                            if st.button("✅ Approve", key=f"arc_ap_{doc['id']}",
                                         use_container_width=True):
                                pob_approve(doc["id"], user_id, comment)
                                st.success("Approved!")
                                st.rerun()
                        with rj:
                            if st.button("❌ Reject", key=f"arc_rj_{doc['id']}",
                                         use_container_width=True):
                                pob_reject(doc["id"], user_id, comment)
                                st.warning("Rejected.")
                                st.rerun()

    st.write("---")
    if st.button("⬅️ Back to Home", key="pob_arc_back"):
        st.session_state.pob_screen = "HOME"
        st.rerun()


# ─────────────────────────────────────────────────────────────
# VIEW DOCUMENT
# ─────────────────────────────────────────────────────────────

def _view_doc(user_id, role):
    doc   = pob_load_document(st.session_state.pob_view_id)
    lines = pob_load_lines(st.session_state.pob_view_id)

    if not doc:
        st.error("Document not found.")
        return

    label = DOC_LABELS.get(doc["doc_type"], "Document")
    icon  = STATUS_ICON.get(doc["status"], "❓")

    st.write(f"### {label} — {doc['pob_no']}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"**Doc No:** {doc['pob_no']}")
        st.write(f"**Date:** {doc['doc_date']}")
    with c2:
        st.write(f"**Party:** {doc['party_name']}")
        st.write(f"**Party Type:** {doc['party_type'].capitalize()}")
    with c3:
        st.write(f"**Status:** {icon} {doc['status'].upper()}")
        if doc.get("approval_comment"):
            st.write(f"**Comment:** {doc['approval_comment']}")

    st.write("---")

    total = 0.0
    for idx, ln in enumerate(lines, 1):
        st.write(f"**{idx}. {ln['product_name']}**")
        r1, r2, r3, r4, r5 = st.columns(5)
        with r1:
            st.write(f"Sale: {ln['sale_qty']}")
            st.write(f"Free: {ln['free_qty']}")
        with r2:
            st.write(f"MRP incl: ₹{float(ln['mrp_incl_tax']):.2f}")
            st.write(f"Tax: {ln['tax_rate']}%")
        with r3:
            st.write(f"Disc: {ln['discount']}%")
            st.write(f"Sales Price: ₹{float(ln['sales_price']):.4f}")
        with r4:
            st.write(f"Tax Amt: ₹{float(ln['tax_amount']):.4f}")
            st.write(f"Gross: ₹{float(ln['gross_rate']):.4f}")
        with r5:
            st.write(f"**Net: ₹{float(ln['net_rate']):.2f}**")
        total += float(ln["net_rate"])
        st.write("---")

    st.success(f"### 💰 Grand Total: ₹{total:.2f}")

    e1, e2, e3 = st.columns(3)
    with e1:
        msg    = pob_format_whatsapp(doc, lines)
        wa_url = "https://wa.me/?text=" + urllib.parse.quote(msg)
        st.link_button("📱 WhatsApp", wa_url, use_container_width=True)
    with e2:
        pdf_bytes = pob_generate_pdf(doc, lines)
        if pdf_bytes:
            st.download_button("📄 PDF", data=pdf_bytes,
                               file_name=f"{doc['pob_no']}.pdf",
                               mime="application/pdf",
                               use_container_width=True)
    with e3:
        if st.button("⬅️ Back to Archive", use_container_width=True,
                     key="pob_view_back"):
            st.session_state.pob_screen = "ARCHIVE"
            st.rerun()


# ─────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────

def _back_home():
    if st.button("🔙 Back to Home", key="pob_back_home_btn"):
        st.session_state.pob_screen = "HOME"
        st.rerun()
