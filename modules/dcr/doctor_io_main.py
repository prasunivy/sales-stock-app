"""
Doctor Input / Output Module
────────────────────────────
Tracks what gifts / inputs were given to each doctor (Form A)
and what sales / output came back (Form B), with a combined
monthly trend report.

Entry point: run_doctor_io()
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO

from modules.dcr.doctor_io_database import (
    get_doctors_for_user,
    get_all_users_active,
    get_user_territories,
    # Form A
    save_admin_input,
    update_admin_input,
    delete_admin_input,
    load_admin_input_session,
    load_dcr_gifts_for_user_month,
    # Form B
    save_doctor_output,
    load_output_session,
    delete_output_record,
    # Report
    load_io_report,
)
from modules.dcr.dcr_helpers import get_current_user_id

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer)
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def _init_io_state():
    defaults = {
        "io_mode": "HOME",           # HOME | FORM_A | FORM_B | REPORT
        "io_sub": "FILL",            # FILL | REVIEW | DONE
        "io_selected_user": None,
        "io_month": date.today().month,
        "io_year": date.today().year,
        "io_doctor_index": 0,
        "io_input_records": [],      # accumulates Form A rows
        "io_output_records": [],     # accumulates Form B rows
        "io_edit_row": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY
# ─────────────────────────────────────────────────────────────────────────────

def run_doctor_io():
    _init_io_state()
    st.title("💊 Doctor Input / Output")

    user_id = get_current_user_id()
    role = st.session_state.get("role", "user")

    mode = st.session_state.io_mode

    if mode == "FORM_A":
        _run_form_a(user_id, role)
    elif mode == "FORM_B":
        _run_form_b(user_id, role)
    elif mode == "REPORT":
        _run_report(user_id, role)
    else:
        _home_screen(role)


# ─────────────────────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────────────────────

def _home_screen(role):
    st.write("### What would you like to do?")
    st.write("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 Doctor Input\n(Gifts Given)", use_container_width=True, type="primary"):
            st.session_state.io_mode = "FORM_A"
            st.session_state.io_sub = "FILL"
            st.session_state.io_input_records = []
            st.session_state.io_doctor_index = 0
            st.rerun()

    with col2:
        if st.button("📤 Doctor Output\n(Sales Report)", use_container_width=True):
            st.session_state.io_mode = "FORM_B"
            st.session_state.io_sub = "FILL"
            st.session_state.io_output_records = []
            st.session_state.io_doctor_index = 0
            st.rerun()

    with col3:
        if st.button("📊 Input / Output Report", use_container_width=True):
            st.session_state.io_mode = "REPORT"
            st.rerun()

    if st.button("⬅️ Back to DCR Home"):
        st.session_state.io_mode = "HOME"
        st.session_state.dcr_masters_mode = None
        st.session_state.dcr_current_step = 0
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# FORM A  –  INPUT
# ─────────────────────────────────────────────────────────────────────────────

def _run_form_a(user_id, role):
    sub = st.session_state.io_sub

    if sub == "FILL":
        _form_a_fill(user_id, role)
    elif sub == "REVIEW":
        _form_a_review(user_id, role)
    elif sub == "DONE":
        _form_a_done(user_id)


def _form_a_fill(user_id, role):
    st.write("### 📥 Doctor Input — Gifts Entry")

    if st.button("⬅️ Back"):
        st.session_state.io_mode = "HOME"
        st.rerun()

    st.write("---")

    # User selection (admin)
    target_user = _select_target_user(user_id, role, "form_a")

    # Month / Year picker
    col1, col2 = st.columns(2)
    with col1:
        sel_month = st.selectbox("Month", list(MONTHS.keys()),
                                 index=st.session_state.io_month - 1,
                                 format_func=lambda x: MONTHS[x],
                                 key="fa_month")
    with col2:
        sel_year = st.number_input("Year", min_value=2020, max_value=2030,
                                   value=st.session_state.io_year, key="fa_year")

    st.session_state.io_month = sel_month
    st.session_state.io_year = sel_year

    # Load doctors
    doctors = get_doctors_for_user(target_user)
    if not doctors:
        st.warning("No doctors found for this user's territories.")
        return

    # Show DCR gifts already in DB for this month (read-only reference)
    dcr_gifts = load_dcr_gifts_for_user_month(target_user, sel_month, sel_year)
    if dcr_gifts:
        with st.expander(f"📋 Gifts already recorded via DCR this month ({len(dcr_gifts)} entries)"):
            dcr_df = pd.DataFrame(dcr_gifts)[["report_date", "doctor_name",
                                               "gift_description", "gift_amount"]]
            dcr_df.columns = ["Date", "Doctor", "Description", "Amount (₹)"]
            st.dataframe(dcr_df, use_container_width=True, hide_index=True)

    st.write("---")
    st.write("#### Enter Gifts for Each Doctor")

    # Current doctor index
    idx = st.session_state.io_doctor_index
    # Clamp
    if idx >= len(doctors):
        idx = len(doctors) - 1
        st.session_state.io_doctor_index = idx

    doc = doctors[idx]
    st.info(f"Doctor **{idx + 1} / {len(doctors)}**: **{doc['name']}** "
            f"({doc.get('specialization', 'N/A')})")

    records_for_doc = [r for r in st.session_state.io_input_records
                       if r["doctor_id"] == doc["id"]]

    # Show existing entries for this doc (current session)
    if records_for_doc:
        st.write("**Already added for this doctor (this session):**")
        for i, rec in enumerate(records_for_doc):
            st.write(f"  • {rec['date']} | {rec['gift_description']} | "
                     f"₹{rec['gift_amount']:.2f} | {rec['amount_kind'].upper()}")

    with st.form(key=f"form_a_{idx}_{doc['id'][:8]}"):
        entry_date = st.date_input("Date *", value=date.today())
        gift_desc  = st.text_input("Gift Description *", placeholder="e.g. Product samples, Pen set")
        col_a, col_b = st.columns(2)
        with col_a:
            gift_amount = st.number_input("Amount (₹) *", min_value=0.0, step=50.0, format="%.2f")
        with col_b:
            amount_kind = st.selectbox("Type", ["cash", "kind"],
                                       help="Cash = monetary value, Kind = physical gift")
        remarks = st.text_input("Remarks", placeholder="Optional notes")

        col_save, col_next, col_skip, col_end = st.columns(4)
        with col_save:
            save_btn = st.form_submit_button("💾 Save & Next ➡️", type="primary")
        with col_next:
            skip_btn = st.form_submit_button("⏭️ Skip Doctor")
        with col_skip:
            reset_btn = st.form_submit_button("🔄 Reset")
        with col_end:
            end_btn = st.form_submit_button("🏁 End Input Entry")

    if save_btn:
        if not gift_desc:
            st.error("Gift description is required.")
        elif gift_amount <= 0:
            st.error("Amount must be greater than zero.")
        else:
            st.session_state.io_input_records.append({
                "doctor_id": doc["id"],
                "doctor_name": doc["name"],
                "date": str(entry_date),
                "gift_description": gift_desc,
                "gift_amount": gift_amount,
                "amount_kind": amount_kind,
                "remarks": remarks
            })
            _advance_doctor(doctors)
            st.rerun()

    if skip_btn:
        _advance_doctor(doctors)
        st.rerun()

    if reset_btn:
        # Remove all entries for this doctor in this session
        st.session_state.io_input_records = [
            r for r in st.session_state.io_input_records
            if r["doctor_id"] != doc["id"]
        ]
        st.rerun()

    if end_btn:
        st.session_state.io_sub = "REVIEW"
        st.rerun()


def _form_a_review(user_id, role):
    st.write("### 📥 Doctor Input — Review Before Final Submit")

    if st.button("⬅️ Back to Entry"):
        st.session_state.io_sub = "FILL"
        st.rerun()

    records = st.session_state.io_input_records

    if not records:
        st.info("No records entered. Nothing to submit.")
        if st.button("🏠 Back to Home"):
            st.session_state.io_mode = "HOME"
            st.rerun()
        return

    target_user = st.session_state.get("io_selected_user") or user_id

    # Build editable table
    st.write(f"**{len(records)} record(s) to be saved for "
             f"{MONTHS[st.session_state.io_month]} {st.session_state.io_year}**")

    for i, rec in enumerate(records):
        with st.expander(f"#{i+1} — {rec['doctor_name']} | {rec['date']} | ₹{rec['gift_amount']:.2f}",
                         expanded=False):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_desc   = st.text_input("Description", value=rec["gift_description"], key=f"ra_desc_{i}")
                new_amount = st.number_input("Amount (₹)", value=rec["gift_amount"],
                                             min_value=0.0, step=50.0, format="%.2f", key=f"ra_amt_{i}")
                new_kind   = st.selectbox("Type", ["cash", "kind"],
                                          index=0 if rec["amount_kind"] == "cash" else 1,
                                          key=f"ra_kind_{i}")
                new_rem    = st.text_input("Remarks", value=rec.get("remarks", ""), key=f"ra_rem_{i}")
                if st.button("✅ Update", key=f"ra_upd_{i}"):
                    records[i]["gift_description"] = new_desc
                    records[i]["gift_amount"]       = new_amount
                    records[i]["amount_kind"]       = new_kind
                    records[i]["remarks"]           = new_rem
                    st.session_state.io_input_records = records
                    st.success("Updated!")
                    st.rerun()
            with col2:
                if st.button("🗑️ Remove", key=f"ra_del_{i}"):
                    records.pop(i)
                    st.session_state.io_input_records = records
                    st.rerun()

    st.write("---")
    if st.button("✅ Final Submit", type="primary"):
        current_user = get_current_user_id()
        errors = 0
        for rec in records:
            try:
                save_admin_input(
                    user_id=target_user,
                    doctor_id=rec["doctor_id"],
                    input_date=date.fromisoformat(rec["date"]),
                    gift_description=rec["gift_description"],
                    gift_amount=rec["gift_amount"],
                    amount_kind=rec["amount_kind"],
                    remarks=rec.get("remarks", ""),
                    created_by=current_user
                )
            except Exception as e:
                st.error(f"Error saving {rec['doctor_name']}: {e}")
                errors += 1

        if errors == 0:
            st.success(f"✅ {len(records)} record(s) saved successfully!")
            st.session_state.io_sub = "DONE"
            st.rerun()


def _form_a_done(user_id):
    st.success("### ✅ Doctor Input Submitted Successfully!")
    st.write(f"Records saved for **{MONTHS[st.session_state.io_month]} "
             f"{st.session_state.io_year}**.")

    # Load saved records to show / export
    target_user = st.session_state.get("io_selected_user") or user_id
    records = load_admin_input_session(target_user,
                                       st.session_state.io_month,
                                       st.session_state.io_year)

    if records:
        df = pd.DataFrame(records)[["date", "doctor_name", "gift_description",
                                     "gift_amount", "amount_kind", "remarks"]]
        df.columns = ["Date", "Doctor", "Description", "Amount (₹)", "Type", "Remarks"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            _pdf_download_btn_input(records, st.session_state.io_month,
                                    st.session_state.io_year)
        with col2:
            _whatsapp_btn_input(records, st.session_state.io_month,
                                st.session_state.io_year)

    if st.button("🏠 Back to Home"):
        st.session_state.io_mode = "HOME"
        st.session_state.io_input_records = []
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# FORM B  –  OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def _run_form_b(user_id, role):
    sub = st.session_state.io_sub
    if sub == "FILL":
        _form_b_fill(user_id, role)
    elif sub == "REVIEW":
        _form_b_review(user_id, role)
    elif sub == "DONE":
        _form_b_done(user_id)


def _form_b_fill(user_id, role):
    st.write("### 📤 Doctor Output — Monthly Sales Entry")

    if st.button("⬅️ Back"):
        st.session_state.io_mode = "HOME"
        st.rerun()

    st.write("---")

    target_user = _select_target_user(user_id, role, "form_b")

    col1, col2 = st.columns(2)
    with col1:
        sel_month = st.selectbox("Month", list(MONTHS.keys()),
                                 index=st.session_state.io_month - 1,
                                 format_func=lambda x: MONTHS[x],
                                 key="fb_month")
    with col2:
        sel_year = st.number_input("Year", min_value=2020, max_value=2030,
                                   value=st.session_state.io_year, key="fb_year")

    st.session_state.io_month = sel_month
    st.session_state.io_year = sel_year

    doctors = get_doctors_for_user(target_user)
    if not doctors:
        st.warning("No doctors found for this user's territories.")
        return

    idx = st.session_state.io_doctor_index
    if idx >= len(doctors):
        idx = len(doctors) - 1
        st.session_state.io_doctor_index = idx

    doc = doctors[idx]
    st.info(f"Doctor **{idx + 1} / {len(doctors)}**: **{doc['name']}** "
            f"({doc.get('specialization', 'N/A')})")

    # Pre-fill if already in session list
    existing = next((r for r in st.session_state.io_output_records
                     if r["doctor_id"] == doc["id"]), None)
    prefill_amount  = existing["sales_amount"] if existing else 0.0
    prefill_remarks = existing["remarks"] if existing else ""

    with st.form(key=f"form_b_{idx}_{doc['id'][:8]}"):
        sales_amount = st.number_input("Output / Sales Amount (₹) *",
                                       min_value=0.0, step=100.0, format="%.2f",
                                       value=prefill_amount)
        remarks = st.text_input("Remarks", value=prefill_remarks,
                                placeholder="Optional notes")

        col_save, col_skip, col_reset, col_end = st.columns(4)
        with col_save:
            save_btn = st.form_submit_button("💾 Save & Next ➡️", type="primary")
        with col_skip:
            skip_btn = st.form_submit_button("⏭️ Skip Doctor")
        with col_reset:
            reset_btn = st.form_submit_button("🔄 Reset")
        with col_end:
            end_btn = st.form_submit_button("🏁 End Output Entry")

    if save_btn:
        # Remove old entry for this doc if exists
        st.session_state.io_output_records = [
            r for r in st.session_state.io_output_records
            if r["doctor_id"] != doc["id"]
        ]
        st.session_state.io_output_records.append({
            "doctor_id": doc["id"],
            "doctor_name": doc["name"],
            "sales_amount": sales_amount,
            "remarks": remarks
        })
        _advance_doctor(doctors)
        st.rerun()

    if skip_btn:
        _advance_doctor(doctors)
        st.rerun()

    if reset_btn:
        st.session_state.io_output_records = [
            r for r in st.session_state.io_output_records
            if r["doctor_id"] != doc["id"]
        ]
        st.rerun()

    if end_btn:
        st.session_state.io_sub = "REVIEW"
        st.rerun()


def _form_b_review(user_id, role):
    st.write("### 📤 Doctor Output — Review Before Final Submit")

    if st.button("⬅️ Back to Entry"):
        st.session_state.io_sub = "FILL"
        st.rerun()

    records = st.session_state.io_output_records

    if not records:
        st.info("No output records entered.")
        if st.button("🏠 Back to Home"):
            st.session_state.io_mode = "HOME"
            st.rerun()
        return

    st.write(f"**{len(records)} doctor(s) for "
             f"{MONTHS[st.session_state.io_month]} {st.session_state.io_year}**")

    for i, rec in enumerate(records):
        with st.expander(f"#{i+1} — {rec['doctor_name']} | ₹{rec['sales_amount']:.2f}",
                         expanded=False):
            col1, col2 = st.columns([4, 1])
            with col1:
                new_amt = st.number_input("Sales Amount (₹)", value=rec["sales_amount"],
                                          min_value=0.0, step=100.0, format="%.2f",
                                          key=f"rb_amt_{i}")
                new_rem = st.text_input("Remarks", value=rec.get("remarks", ""),
                                        key=f"rb_rem_{i}")
                if st.button("✅ Update", key=f"rb_upd_{i}"):
                    records[i]["sales_amount"] = new_amt
                    records[i]["remarks"] = new_rem
                    st.session_state.io_output_records = records
                    st.success("Updated!")
                    st.rerun()
            with col2:
                if st.button("🗑️ Remove", key=f"rb_del_{i}"):
                    records.pop(i)
                    st.session_state.io_output_records = records
                    st.rerun()

    st.write("---")
    if st.button("✅ Final Submit", type="primary"):
        target_user = st.session_state.get("io_selected_user") or user_id
        current_user = get_current_user_id()
        errors = 0
        for rec in records:
            try:
                save_doctor_output(
                    user_id=target_user,
                    doctor_id=rec["doctor_id"],
                    month=st.session_state.io_month,
                    year=st.session_state.io_year,
                    sales_amount=rec["sales_amount"],
                    remarks=rec.get("remarks", ""),
                    created_by=current_user
                )
            except Exception as e:
                st.error(f"Error saving {rec['doctor_name']}: {e}")
                errors += 1

        if errors == 0:
            st.success(f"✅ {len(records)} record(s) saved!")
            st.session_state.io_sub = "DONE"
            st.rerun()


def _form_b_done(user_id):
    st.success("### ✅ Doctor Output Submitted Successfully!")
    st.write(f"Records saved for **{MONTHS[st.session_state.io_month]} "
             f"{st.session_state.io_year}**.")

    target_user = st.session_state.get("io_selected_user") or user_id
    records = load_output_session(target_user,
                                  st.session_state.io_month,
                                  st.session_state.io_year)

    if records:
        df = pd.DataFrame(records)[["doctor_name", "sales_amount", "remarks"]]
        df.columns = ["Doctor", "Sales Amount (₹)", "Remarks"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            _pdf_download_btn_output(records, st.session_state.io_month,
                                     st.session_state.io_year)
        with col2:
            _whatsapp_btn_output(records, st.session_state.io_month,
                                 st.session_state.io_year)

    if st.button("🏠 Back to Home"):
        st.session_state.io_mode = "HOME"
        st.session_state.io_output_records = []
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────────────────────

def _run_report(user_id, role):
    st.write("### 📊 Doctor Input / Output Report")

    if st.button("⬅️ Back to Home"):
        st.session_state.io_mode = "HOME"
        st.rerun()

    st.write("---")

    target_user = _select_target_user(user_id, role, "report")

    col1, col2, col3 = st.columns(3)
    with col1:
        sel_year = st.number_input("Year", min_value=2020, max_value=2030,
                                   value=date.today().year, key="rpt_year")
    with col2:
        month_options = {0: "All Months", **MONTHS}
        sel_month_filter = st.selectbox("Month Filter", list(month_options.keys()),
                                        format_func=lambda x: month_options[x],
                                        key="rpt_month")
    with col3:
        st.write("")
        st.write("")
        load_btn = st.button("🔍 Load Report", type="primary")

    if not load_btn:
        st.info("Select filters and click **Load Report**.")
        return

    months = list(range(1, 13)) if sel_month_filter == 0 else [sel_month_filter]

    with st.spinner("Loading report..."):
        report_data = load_io_report(target_user, sel_year, months)

    if not report_data:
        st.warning("No data found for selected filters.")
        return

    # ── Build pivot table ─────────────────────────────────────────────────────
    # Columns: Doctor | Jan Input | Jan Output | Feb Input | Feb Output | ...
    col_headers = ["Doctor"]
    for mo in months:
        mname = MONTHS[mo][:3]
        col_headers += [f"{mname} Input (₹)", f"{mname} Output (₹)"]

    rows = []
    for did, info in sorted(report_data.items(), key=lambda x: x[1]["doctor_name"]):
        row = [info["doctor_name"]]
        for mo in months:
            key = (mo, sel_year)
            cell = info["data"].get(key, {})
            row.append(f"₹{cell.get('total_input', 0):,.2f}")
            row.append(f"₹{cell.get('output', 0):,.2f}")
        rows.append(row)

    df = pd.DataFrame(rows, columns=col_headers)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Detail breakdown ──────────────────────────────────────────────────────
    with st.expander("📋 Input Detail Breakdown (Cash / Kind / DCR Gifts)"):
        detail_cols = ["Doctor"]
        for mo in months:
            mname = MONTHS[mo][:3]
            detail_cols += [f"{mname} Cash", f"{mname} Kind",
                            f"{mname} DCR Gift", f"{mname} Total Input"]

        detail_rows = []
        for did, info in sorted(report_data.items(), key=lambda x: x[1]["doctor_name"]):
            row = [info["doctor_name"]]
            for mo in months:
                key = (mo, sel_year)
                cell = info["data"].get(key, {})
                row += [
                    f"₹{cell.get('input_cash', 0):,.2f}",
                    f"₹{cell.get('input_kind', 0):,.2f}",
                    f"₹{cell.get('dcr_gift', 0):,.2f}",
                    f"₹{cell.get('total_input', 0):,.2f}",
                ]
            detail_rows.append(row)

        df_detail = pd.DataFrame(detail_rows, columns=detail_cols)
        st.dataframe(df_detail, use_container_width=True, hide_index=True)

    # PDF export
    st.write("---")
    col_pdf, col_wa = st.columns(2)
    with col_pdf:
        _pdf_download_btn_report(report_data, months, sel_year)
    with col_wa:
        _whatsapp_btn_report(report_data, months, sel_year)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _advance_doctor(doctors):
    """Move to next doctor or wrap around."""
    idx = st.session_state.io_doctor_index + 1
    if idx >= len(doctors):
        idx = 0
    st.session_state.io_doctor_index = idx


def _select_target_user(user_id, role, key_suffix):
    """
    If admin, show user dropdown and store selection.
    Returns the effective user_id to use.
    """
    if role == "admin":
        users = get_all_users_active()
        user_map = {u["id"]: u["username"] for u in users}
        stored = st.session_state.get("io_selected_user") or user_id
        sel = st.selectbox(
            "Select User (Admin)",
            options=list(user_map.keys()),
            format_func=lambda x: user_map.get(x, x),
            index=list(user_map.keys()).index(stored) if stored in user_map else 0,
            key=f"io_user_{key_suffix}"
        )
        st.session_state.io_selected_user = sel
        return sel
    else:
        st.session_state.io_selected_user = user_id
        return user_id


# ─────────────────────────────────────────────────────────────────────────────
# PDF GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _make_pdf_input(records, month, year):
    if not REPORTLAB_OK:
        return None
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("Ivy Pharmaceuticals", styles["Title"]))
    elems.append(Paragraph(f"Doctor Input Report — {MONTHS[month]} {year}",
                            styles["Heading2"]))
    elems.append(Spacer(1, 0.4*cm))

    data = [["Date", "Doctor", "Description", "Amount (₹)", "Type", "Remarks"]]
    total = 0.0
    for r in records:
        data.append([r["date"], r["doctor_name"], r["gift_description"],
                     f"₹{r['gift_amount']:,.2f}", r["amount_kind"].upper(),
                     r.get("remarks", "")])
        total += r["gift_amount"]
    data.append(["", "TOTAL", "", f"₹{total:,.2f}", "", ""])

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a6b5a")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f4f2")),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elems.append(tbl)

    doc.build(elems)
    buf.seek(0)
    return buf


def _make_pdf_output(records, month, year):
    if not REPORTLAB_OK:
        return None
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=1.5*cm, rightMargin=1.5*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("Ivy Pharmaceuticals", styles["Title"]))
    elems.append(Paragraph(f"Doctor Output Report — {MONTHS[month]} {year}",
                            styles["Heading2"]))
    elems.append(Spacer(1, 0.4*cm))

    data = [["Doctor", "Sales Amount (₹)", "Remarks"]]
    total = 0.0
    for r in records:
        data.append([r["doctor_name"], f"₹{r['sales_amount']:,.2f}",
                     r.get("remarks", "")])
        total += r["sales_amount"]
    data.append(["TOTAL", f"₹{total:,.2f}", ""])

    tbl = Table(data, repeatRows=1, colWidths=[7*cm, 5*cm, 7*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a4fa6")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8eef8")),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elems.append(tbl)

    doc.build(elems)
    buf.seek(0)
    return buf


def _make_pdf_report(report_data, months, year):
    if not REPORTLAB_OK:
        return None
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=1*cm, rightMargin=1*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elems = []

    month_str = (f"{MONTHS[months[0]]}–{MONTHS[months[-1]]}" if len(months) > 1
                 else MONTHS[months[0]])
    elems.append(Paragraph("Ivy Pharmaceuticals", styles["Title"]))
    elems.append(Paragraph(f"Doctor Input/Output Report — {month_str} {year}",
                            styles["Heading2"]))
    elems.append(Spacer(1, 0.4*cm))

    header = ["Doctor"]
    for mo in months:
        header += [f"{MONTHS[mo][:3]} Input", f"{MONTHS[mo][:3]} Output"]

    data = [header]
    for did, info in sorted(report_data.items(), key=lambda x: x[1]["doctor_name"]):
        row = [info["doctor_name"]]
        for mo in months:
            key = (mo, year)
            cell = info["data"].get(key, {})
            row += [f"₹{cell.get('total_input', 0):,.0f}",
                    f"₹{cell.get('output', 0):,.0f}"]
        data.append(row)

    col_count = len(header)
    col_w = [5*cm] + [2.5*cm] * (col_count - 1)

    tbl = Table(data, repeatRows=1, colWidths=col_w)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 7),
        ("GRID",       (0, 0), (-1, -1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elems.append(tbl)

    doc.build(elems)
    buf.seek(0)
    return buf


def _pdf_download_btn_input(records, month, year):
    buf = _make_pdf_input(records, month, year)
    if buf:
        st.download_button("📄 Download PDF", data=buf,
                           file_name=f"doctor_input_{MONTHS[month]}_{year}.pdf",
                           mime="application/pdf")
    else:
        st.info("Install reportlab for PDF export.")


def _pdf_download_btn_output(records, month, year):
    buf = _make_pdf_output(records, month, year)
    if buf:
        st.download_button("📄 Download PDF", data=buf,
                           file_name=f"doctor_output_{MONTHS[month]}_{year}.pdf",
                           mime="application/pdf")
    else:
        st.info("Install reportlab for PDF export.")


def _pdf_download_btn_report(report_data, months, year):
    buf = _make_pdf_report(report_data, months, year)
    if buf:
        mstr = MONTHS[months[0]] if len(months) == 1 else f"{MONTHS[months[0]]}-{MONTHS[months[-1]]}"
        st.download_button("📄 Download Report PDF", data=buf,
                           file_name=f"io_report_{mstr}_{year}.pdf",
                           mime="application/pdf")
    else:
        st.info("Install reportlab for PDF export.")


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP
# ─────────────────────────────────────────────────────────────────────────────

def _whatsapp_btn_input(records, month, year):
    lines = [f"*Doctor Input Report — {MONTHS[month]} {year}*",
             f"Ivy Pharmaceuticals", ""]
    total = 0.0
    for r in records:
        lines.append(f"• {r['doctor_name']} | {r['date']} | "
                     f"₹{r['gift_amount']:,.2f} ({r['amount_kind'].upper()})")
        total += r["gift_amount"]
    lines += ["", f"*Total Input: ₹{total:,.2f}*"]
    msg = "%0A".join(lines)
    st.link_button("📱 Share via WhatsApp",
                   url=f"https://wa.me/?text={msg}")


def _whatsapp_btn_output(records, month, year):
    lines = [f"*Doctor Output Report — {MONTHS[month]} {year}*",
             f"Ivy Pharmaceuticals", ""]
    total = 0.0
    for r in records:
        lines.append(f"• {r['doctor_name']} | ₹{r['sales_amount']:,.2f}")
        total += r["sales_amount"]
    lines += ["", f"*Total Output: ₹{total:,.2f}*"]
    msg = "%0A".join(lines)
    st.link_button("📱 Share via WhatsApp",
                   url=f"https://wa.me/?text={msg}")


def _whatsapp_btn_report(report_data, months, year):
    month_str = (f"{MONTHS[months[0]]}–{MONTHS[months[-1]]}" if len(months) > 1
                 else MONTHS[months[0]])
    lines = [f"*Doctor I/O Report — {month_str} {year}*",
             "Ivy Pharmaceuticals", ""]
    for did, info in sorted(report_data.items(), key=lambda x: x[1]["doctor_name"]):
        total_in = sum(info["data"].get((mo, year), {}).get("total_input", 0) for mo in months)
        total_out = sum(info["data"].get((mo, year), {}).get("output", 0) for mo in months)
        lines.append(f"• {info['doctor_name']} | In: ₹{total_in:,.0f} | Out: ₹{total_out:,.0f}")
    msg = "%0A".join(lines)
    st.link_button("📱 Share via WhatsApp",
                   url=f"https://wa.me/?text={msg}")
