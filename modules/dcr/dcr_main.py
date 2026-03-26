"""
DCR Main Module - Daily Call Report
Complete implementation with all 4 stages
"""

import streamlit as st
from datetime import date, datetime
from modules.dcr.dcr_database import (
    init_dcr_session_state,
    check_duplicate_dcr,
    create_dcr_draft,
    save_dcr_header,
    save_doctor_visit,
    save_chemist_visits,
    save_gift,
    save_expenses,
    submit_dcr_final,
    delete_dcr_soft,
    get_dcr_by_id,
    get_user_territories,
    get_doctors_by_territories,
    get_chemists_by_territories,
    get_products_all,
    get_managers_list,
    load_dcr_monthly_reports,
    remove_doctor_visit,
    remove_gift
)
from modules.dcr.dcr_helpers import (
    format_whatsapp_message,
    validate_date,
    get_current_user_id
)
from modules.dcr.doctors_master import run_doctors_master
from modules.dcr.chemists_master import run_chemists_master
from modules.dcr.doctor_io_main import run_doctor_io


def run_dcr():
    """Main entry point for DCR module"""
    init_dcr_session_state()
    
    # Always show home screen on fresh entry
    if (not st.session_state.get("dcr_masters_mode")
        and not st.session_state.get("dcr_report_id")
        and not st.session_state.get("dcr_submit_done")
        and not st.session_state.get("dcr_new_report")):
        st.session_state.dcr_current_step = 0
    
    st.title("📞 Daily Call Report")
    
    try:
        user_id = get_current_user_id()
        role = st.session_state.get("role", "user")
    except Exception as e:
        st.error(f"❌ Authentication Error: {str(e)}")
        st.stop()
    
    # Check if in masters mode
    if st.session_state.get("dcr_masters_mode") == "DOCTORS":
        run_doctors_master()
        return
    
    if st.session_state.get("dcr_masters_mode") == "CHEMISTS":
        run_chemists_master()
        return
    
    if st.session_state.get("dcr_masters_mode") == "DOCTOR_IO":
        run_doctor_io()
        return

    if st.session_state.get("dcr_masters_mode") == "EXPENSE_REPORT":
        show_expense_report()
        return
    
    # Route based on state
    if st.session_state.get("dcr_submit_done"):
        show_post_submit_screen()
    elif st.session_state.get("dcr_current_step", 0) >= 1:
        show_dcr_flow()
    else:
        show_home_screen()


def _get_all_users():
    """Get all active users for admin dropdown."""
    from anchors.supabase_client import admin_supabase, safe_exec
    return safe_exec(
        admin_supabase.table("users")
        .select("id, username")
        .eq("is_active", True)
        .order("username"),
        "Error loading users"
    )


def _get_user_draft(user_id):
    """Check if a draft DCR exists for this user. Returns the draft or None."""
    from anchors.supabase_client import admin_supabase, safe_exec
    result = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("id, report_date, area_type, current_step")
        .eq("user_id", user_id)
        .eq("status", "draft")
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .limit(1),
        "Error checking draft DCR"
    )
    return result[0] if result else None


def show_home_screen():
    """Home screen with DCR options and Masters"""
    st.write("### What would you like to do?")
    
    user_id = get_current_user_id()
    
    # ── Check for existing draft and show resume button ──────────
    existing_draft = _get_user_draft(user_id)
    if existing_draft:
        st.warning(
            f"⚠️ You have an **unfinished DCR** for **{existing_draft['report_date']}** "
            f"(Area: {existing_draft['area_type']}). Resume it below."
        )
        if st.button("▶️ Resume Unfinished DCR", type="primary", use_container_width=True):
            st.session_state.dcr_report_id = existing_draft["id"]
            # Resume from the step it was left at (minimum step 1)
            resume_step = existing_draft.get("current_step") or 1
            if resume_step < 1:
                resume_step = 1
            st.session_state.dcr_current_step = resume_step
            st.session_state.dcr_new_report = False
            st.rerun()
        st.write("---")
    
    # DCR Actions
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("➕ New Daily Report", type="primary" if not existing_draft else "secondary", use_container_width=True):
            st.session_state.dcr_current_step = 1
            st.session_state.dcr_new_report = True
            st.rerun()
    
    with col2:
        if st.button("📅 View My Reports", use_container_width=True):
            st.session_state.dcr_show_history = True
            st.rerun()
    
    # Show history inline if requested
    if st.session_state.get("dcr_show_history"):
        show_monthly_history()
        return
    
    # Masters Section
    st.write("---")
    st.write("### 📚 Masters (Manage Data)")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("👨‍⚕️ Doctors Master", use_container_width=True):
            st.session_state.dcr_masters_mode = "DOCTORS"
            st.rerun()
    
    with col4:
        if st.button("🏪 Chemists Master", use_container_width=True):
            st.session_state.dcr_masters_mode = "CHEMISTS"
            st.rerun()

    # Doctor Input / Output section
    st.write("---")
    st.write("### 💊 Doctor Tracking")
    col5, col6 = st.columns(2)

    with col5:
        if st.button("📊 Doctor Input / Output", use_container_width=True, type="primary"):
            st.session_state.dcr_masters_mode = "DOCTOR_IO"
            st.session_state.io_mode = "HOME"
            st.rerun()

    with col6:
        st.write("")   # placeholder for future buttons

    # Admin-only section
    role = st.session_state.get("role", "user")
    if role == "admin":
        st.write("---")
        st.write("### 📊 Admin Reports")
        if st.button("💰 Expense Calculation", use_container_width=True, type="primary"):
            st.session_state.dcr_masters_mode = "EXPENSE_REPORT"
            st.rerun()


def show_monthly_history():
    """Show monthly DCR history — works for both users and admins."""
    st.write("---")
    st.write("### 📅 DCR History")
    
    current_user_id = get_current_user_id()
    role = st.session_state.get("role", "user")
    
    # ── Admin: pick which user's reports to view ─────────────────
    view_user_id = current_user_id
    if role == "admin":
        users = _get_all_users()
        user_map = {u["id"]: u["username"] for u in users}
        stored = st.session_state.get("dcr_history_user_id") or current_user_id
        selected = st.selectbox(
            "👤 View reports for user:",
            options=list(user_map.keys()),
            format_func=lambda x: user_map.get(x, x),
            index=list(user_map.keys()).index(stored) if stored in user_map else 0,
            key="dcr_history_user_select"
        )
        st.session_state.dcr_history_user_id = selected
        view_user_id = selected
        st.write("---")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        selected_month = st.selectbox(
            "Month",
            options=list(range(1, 13)),
            format_func=lambda x: datetime(2000, x, 1).strftime("%B"),
            index=datetime.now().month - 1,
            key="dcr_hist_month"
        )
    
    with col2:
        selected_year = st.selectbox(
            "Year",
            options=list(range(2020, 2031)),
            index=datetime.now().year - 2020,
            key="dcr_hist_year"
        )
    
    with col3:
        st.write("")
        if st.button("🔄 Refresh"):
            st.rerun()
    
    reports = load_dcr_monthly_reports(view_user_id, selected_year, selected_month)
    
    if not reports:
        st.info(f"No reports found for {datetime(2000, selected_month, 1).strftime('%B')} {selected_year}.")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_show_history = False
            st.session_state.dcr_current_step = 0
            st.rerun()
        return
    
    # ── Split into submitted and drafts ──────────────────────────
    submitted = [r for r in reports if r["status"] == "submitted"]
    drafts    = [r for r in reports if r["status"] == "draft"]
    
    # Show submitted reports
    if submitted:
        st.write(f"**✅ Submitted ({len(submitted)} day(s))**")
        for report in submitted:
            with st.expander(f"📋 {report['report_date']} — {report['area_type']}"):
                st.write(f"📍 Doctors: {report.get('doctor_count', 0)}")
                st.write(f"🏪 Chemists: {report.get('chemist_count', 0)}")
                st.write(f"🎁 Gifts: {report.get('gift_count', 0)}")
                st.write(f"🚗 KM: {report.get('km_travelled', 0)}")
                st.write(f"💰 Expenses: ₹{report.get('misc_expense', 0)}")
    
    # Show draft reports with Resume button
    if drafts:
        st.write(f"**⏳ Drafts — Not Yet Submitted ({len(drafts)} day(s))**")
        for report in drafts:
            with st.expander(f"🟡 {report['report_date']} — {report['area_type']} (DRAFT)"):
                st.write(f"📍 Doctors: {report.get('doctor_count', 0)}")
                st.write(f"🏪 Chemists: {report.get('chemist_count', 0)}")
                st.write(f"🚗 KM: {report.get('km_travelled', 0)}")
                st.warning("This DCR has not been submitted yet.")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("▶️ Resume & Complete", key=f"resume_{report['id']}"):
                        st.session_state.dcr_report_id = report["id"]
                        resume_step = report.get("current_step") or 1
                        if resume_step < 1:
                            resume_step = 1
                        st.session_state.dcr_current_step = resume_step
                        st.session_state.dcr_new_report = False
                        st.session_state.dcr_show_history = False
                        st.rerun()
                with col_b:
                    if st.button("🗑️ Delete Draft", key=f"del_draft_{report['id']}"):
                        delete_dcr_soft(report["id"], current_user_id)
                        st.success("Draft deleted.")
                        st.rerun()
    
    if st.button("⬅️ Back to Home"):
        st.session_state.dcr_show_history = False
        st.session_state.dcr_current_step = 0
        st.rerun()


def show_dcr_flow():
    """Route to appropriate stage"""
    step = st.session_state.get("dcr_current_step", 1)
    
    if step == 1:
        show_stage_1_header()
    elif step == 2:
        show_stage_2_visits()
    elif step == 3:
        show_stage_3_expenses()
    elif step == 4:
        show_stage_4_preview()

def show_stage_1_header():
    """Stage 1: Basic Information"""
    st.write("### Stage 1/4: Basic Information")
    
    if st.session_state.get("dcr_report_id"):
        st.info("ℹ️ **Editing existing DCR** - You can modify the details below")
    
    try:
        current_user_id = get_current_user_id()
    except:
        st.error("Unable to get user ID")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_current_step = 0
            st.session_state.active_module = None
            st.rerun()
        return
    
    selected_user_id = current_user_id
    
    # Date picker
    report_date = st.date_input(
        "Report Date",
        value=date.today(),
        max_value=date.today(),
        help="Cannot select future dates"
    )
    
    if report_date > date.today():
        st.error("❌ Cannot create DCR for future date")
        return
    
    # Check duplicate only if creating NEW DCR (not editing)
    if not st.session_state.get("dcr_report_id"):
        if check_duplicate_dcr(selected_user_id, report_date):
            st.error("❌ A DCR already exists for this date. Please check View My Reports.")
            if st.button("⬅️ Back to Home"):
                st.session_state.dcr_current_step = 0
                st.session_state.active_module = None
                st.rerun()
            return
    else:
        existing_dcr = get_dcr_by_id(st.session_state.dcr_report_id)
        if existing_dcr and str(existing_dcr.get('report_date')) != str(report_date):
            if check_duplicate_dcr(selected_user_id, report_date):
                st.error("❌ Another DCR already exists for this date. Cannot change to this date.")
                return
    
    # Area type
    area_type = st.radio(
        "Area Type",
        options=["HQ", "EX_STATION", "OUTSTATION", "MEETING"],
        format_func=lambda x: {
            "HQ": "🏢 Headquarters",
            "EX_STATION": "🚉 Ex-Station",
            "OUTSTATION": "🌍 Outstation",
            "MEETING": "👥 Meeting"
        }[x],
        horizontal=True
    )
    
    # Territory selection
    selected_territories = []
    if area_type != "MEETING":
        st.write("**Select Territories**")
        
        user_territories = get_user_territories(current_user_id)
        
        if not user_territories:
            st.warning("⚠️ No territories assigned")
            st.info("**For testing:** Select MEETING area type")
            return
        
        selected_territories = st.multiselect(
            "Territories worked today",
            options=[t['id'] for t in user_territories],
            format_func=lambda x: next((t['name'] for t in user_territories if t['id'] == x), x)
        )
        
        if not selected_territories:
            st.warning("⚠️ Please select at least one territory")
            return
    
    # Buttons
    st.write("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Save & Next", type="primary", use_container_width=True):
            try:
                if not st.session_state.get("dcr_report_id"):
                    dcr_id = create_dcr_draft(
                        user_id=selected_user_id,
                        report_date=report_date,
                        area_type=area_type,
                        territory_ids=selected_territories,
                        created_by=current_user_id
                    )
                    st.session_state.dcr_report_id = dcr_id
                    st.session_state.dcr_new_report = False
                else:
                    save_dcr_header(
                        dcr_id=st.session_state.dcr_report_id,
                        area_type=area_type,
                        territory_ids=selected_territories
                    )
                
                st.session_state.dcr_user_id = selected_user_id
                st.session_state.dcr_report_date = report_date
                st.session_state.dcr_area_type = area_type
                st.session_state.dcr_territory_ids = selected_territories
                
                if area_type == "MEETING":
                    st.session_state.dcr_current_step = 3
                else:
                    st.session_state.dcr_current_step = 2
                
                st.success("✅ Saved!")
                st.rerun()
            
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    with col2:
        if st.button("🏠 Back to Home", use_container_width=True):
            st.session_state.dcr_current_step = 0
            st.session_state.dcr_report_id = None
            st.session_state.dcr_new_report = False
            st.session_state.dcr_show_history = False
            st.session_state.engine_stage = None
            st.session_state.active_module = None
            st.rerun()

def show_stage_2_visits():
    """Stage 2: Doctor Visits + Chemist Visits + Gifts"""
    st.write("### Stage 2/4: Visits & Gifts")
    
    dcr_id = st.session_state.dcr_report_id
    territory_ids = st.session_state.dcr_territory_ids
    
    dcr_data = get_dcr_by_id(dcr_id)
    existing_visits = dcr_data.get('doctor_visits', [])
    existing_gifts = dcr_data.get('gifts', [])
    
    # ========================================
    # DOCTORS SECTION
    # ========================================
    st.write("---")
    st.write("#### 👨‍⚕️ Doctor Visits")
    
    doctors = get_doctors_by_territories(territory_ids)
    products = get_products_all()
    managers = get_managers_list()
    
    if not doctors:
        st.warning("⚠️ No doctors found in selected territories")
    else:
        existing_visits = dcr_data.get('doctor_visits', [])
        if existing_visits:
            st.write(f"**Added: {len(existing_visits)} doctor(s)**")
            for idx, visit in enumerate(existing_visits):
                with st.expander(f"Dr. {visit['doctor_name']}"):
                    st.write(f"**Products:** {', '.join(visit['product_names'])}")
                    st.write(f"**Visited with:** {visit.get('visited_with', 'Single')}")
                    if st.button(f"🗑️ Remove", key=f"remove_doc_{idx}"):
                        remove_doctor_visit(visit['id'])
                        st.rerun()
        
        added_doctor_ids = [v['doctor_id'] for v in existing_visits]
        available_doctors = [d for d in doctors if d['id'] not in added_doctor_ids]
        
        if not available_doctors:
            st.info("✅ All doctors in this territory have been added")
        else:
            with st.form("add_doctor_form"):
                st.write("**Add Doctor Visit**")
                
                doctor_options = [None] + [d['id'] for d in available_doctors]
                
                selected_doctor = st.selectbox(
                    "Select Doctor *",
                    options=doctor_options,
                    format_func=lambda x: "-- Select a doctor --" if x is None else next((f"{d['name']} ({d.get('specialization', 'N/A')})" for d in available_doctors if d['id'] == x), x),
                    index=0
                )
                
                selected_products = st.multiselect(
                    "Products Promoted *",
                    options=[p['id'] for p in products],
                    format_func=lambda x: next((p['name'] for p in products if p['id'] == x), x),
                    help="Select one or more products"
                )
                
                visited_with_options = ["single"] + [m['id'] for m in managers]
                visited_with = st.multiselect(
                    "Visited With * (Required)",
                    options=visited_with_options,
                    format_func=lambda x: "Self (Alone)" if x == "single" else next((m['username'] for m in managers if m['id'] == x), x),
                    help="Select 'Self' if alone, or select who accompanied you"
                )
                
                submit_doctor = st.form_submit_button("➕ Add Doctor")
                
                if submit_doctor:
                    if selected_doctor is None:
                        st.error("❌ Please select a doctor")
                    elif not selected_products:
                        st.error("❌ Please select at least one product")
                    elif not visited_with:
                        st.error("❌ Please select who you visited with (required)")
                    else:
                        save_doctor_visit(
                            dcr_id=dcr_id,
                            doctor_id=selected_doctor,
                            product_ids=selected_products,
                            visited_with=",".join(visited_with)
                        )
                        st.success("✅ Doctor visit added!")
                        st.rerun()
    
    # ========================================
    # CHEMISTS SECTION
    # ========================================
    st.write("---")
    st.write("#### 🏪 Chemist Visits")
    
    chemists = get_chemists_by_territories(territory_ids)
    
    if not chemists:
        st.warning("⚠️ No chemists found in selected territories")
    else:
        existing_chemist_ids = dcr_data.get('chemist_ids', [])
        
        if not isinstance(existing_chemist_ids, list):
            existing_chemist_ids = []
        
        valid_chemist_ids = [c['id'] for c in chemists]
        safe_defaults = [cid for cid in existing_chemist_ids if cid in valid_chemist_ids]
        
        selected_chemists = st.multiselect(
            "Select Chemists Visited",
            options=valid_chemist_ids,
            format_func=lambda x: next((c['name'] for c in chemists if c['id'] == x), x),
            default=safe_defaults,
            help="Check the chemists you visited today. You can select multiple."
        )
        
        st.info(f"✓ Selected: {len(selected_chemists)} chemist(s)")
        
        if st.button("💾 Save Chemists"):
            save_chemist_visits(dcr_id, selected_chemists)
            st.success("Chemist visits saved!")
            st.rerun()
    
    # ========================================
    # GIFTS SECTION
    # ========================================
    st.write("---")
    st.write("#### 🎁 Gifts (Optional)")

    existing_gifts = dcr_data.get('gifts', [])
    existing_visits_fresh = dcr_data.get('doctor_visits', [])

    if existing_gifts:
        st.write(f"**Added: {len(existing_gifts)} gift(s)**")
        for idx, gift in enumerate(existing_gifts):
            with st.expander(f"Dr. {gift['doctor_name']} - ₹{gift['gift_amount']}"):
                st.write(f"**Gift:** {gift['gift_description']}")
                if st.button(f"🗑️ Remove", key=f"remove_gift_{idx}"):
                    remove_gift(gift['id'])
                    st.rerun()

    if not existing_visits_fresh:
        st.info("ℹ️ Add doctor visits above first to record gifts")
    else:
        with st.form("add_gift_form"):
            st.write("**Add Gift**")

            gift_doctor_options = [None] + [v['doctor_id'] for v in existing_visits_fresh]

            gift_doctor = st.selectbox(
                "Select Doctor *",
                options=gift_doctor_options,
                format_func=lambda x: "-- Select a doctor --" if x is None else next(
                    (v['doctor_name'] for v in existing_visits_fresh if v['doctor_id'] == x), "Unknown"
                ),
                index=0
            )

            gift_description = st.text_input(
                "Gift Description *",
                placeholder="e.g., Medical Books, Calendar, Pen Set"
            )

            gift_amount = st.number_input(
                "Gift Amount (₹) *",
                min_value=0.0,
                step=10.0
            )

            submit_gift = st.form_submit_button("➕ Add Gift")

            if submit_gift:
                if gift_doctor is None:
                    st.error("❌ Please select a doctor")
                elif not gift_description or not gift_description.strip():
                    st.error("❌ Please enter gift description")
                elif gift_amount <= 0:
                    st.error("❌ Gift amount must be greater than zero")
                else:
                    save_gift(dcr_id, gift_doctor, gift_description, gift_amount)
                    st.success("✅ Gift added!")
                    st.rerun()
    
    # Navigation
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state.dcr_current_step = 1
            st.rerun()
    with col2:
        if st.button("💾 Save & Next ➡️", type="primary"):
            st.session_state.dcr_current_step = 3
            st.rerun()

def show_stage_3_expenses():
    """Stage 3: Expenses"""
    st.write("### Stage 3/4: Expenses")
    
    dcr_id = st.session_state.dcr_report_id
    dcr_data = get_dcr_by_id(dcr_id)
    
    km_travelled = st.number_input(
        "🚗 KM Travelled",
        min_value=0.0,
        step=1.0,
        value=float(dcr_data.get('km_travelled', 0))
    )
    
    misc_expense = st.number_input(
        "💰 Miscellaneous Expense (₹)",
        min_value=0.0,
        step=10.0,
        value=float(dcr_data.get('misc_expense', 0))
    )
    
    misc_expense_details = st.text_area(
        "📝 Expense Details (Optional)",
        value=dcr_data.get('misc_expense_details', ''),
        placeholder="e.g., Parking, Toll, Food"
    )
    
    st.write("---")
    st.write("**Preview:**")
    st.write(f"🚗 KM: {km_travelled}")
    st.write(f"💰 Misc Expense: ₹{misc_expense}")
    if misc_expense_details:
        st.write(f"📝 Details: {misc_expense_details}")
    
    st.write("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Previous"):
            if st.session_state.dcr_area_type == "MEETING":
                st.session_state.dcr_current_step = 1
            else:
                st.session_state.dcr_current_step = 2
            st.rerun()
    with col2:
        if st.button("💾 Save & Next ➡️", type="primary"):
            save_expenses(dcr_id, km_travelled, misc_expense, misc_expense_details)
            st.session_state.dcr_current_step = 4
            st.rerun()

def show_stage_4_preview():
    """Stage 4: Preview & Submit"""
    st.write("### Stage 4/4: Preview & Submit")
    
    dcr_id = st.session_state.get("dcr_report_id")
    
    if not dcr_id:
        st.error("❌ No DCR found. Please start over.")
        if st.button("🏠 Back to Home"):
            st.session_state.dcr_current_step = 0
            st.session_state.active_module = None
            st.rerun()
        return
    
    try:
        dcr_data = get_dcr_by_id(dcr_id)
    except Exception as e:
        st.error(f"❌ Error loading DCR: {str(e)}")
        if st.button("🏠 Back to Home"):
            st.session_state.dcr_report_id = None
            st.session_state.dcr_current_step = 0
            st.session_state.active_module = None
            st.rerun()
        return
    
    if not dcr_data or not dcr_data.get('report_date'):
        st.error("❌ DCR data is incomplete or corrupted")
        if st.button("🏠 Back to Home"):
            st.session_state.dcr_report_id = None
            st.session_state.dcr_current_step = 0
            st.session_state.active_module = None
            st.rerun()
        return
    
    st.write("---")
    st.write("#### 📋 DCR Summary")
    st.write(f"**Date:** {dcr_data['report_date']}")
    st.write(f"**Area:** {dcr_data['area_type']}")
    
    if dcr_data.get('territory_names'):
        st.write(f"**Territories:** {', '.join(dcr_data['territory_names'])}")
    
    st.write("---")
    st.write("**👨‍⚕️ Doctor Visits:**")
    doctor_visits = dcr_data.get('doctor_visits', [])
    if doctor_visits:
        for visit in doctor_visits:
            visited_with_raw = visit.get('visited_with', 'single')
            if visited_with_raw == 'single' or not visited_with_raw:
                visited_with_display = "Self (Alone)"
            else:
                ids = visited_with_raw.split(',')
                managers = get_managers_list()
                names = []
                for id_val in ids:
                    if id_val == 'single':
                        names.append("Self")
                    else:
                        manager_name = next((m['username'] for m in managers if m['id'] == id_val), id_val)
                        names.append(manager_name)
                visited_with_display = ', '.join(names)
        
            st.write(f"• Dr. {visit['doctor_name']}")
            st.write(f"  Products: {', '.join(visit['product_names'])}")
            st.write(f"  With: {visited_with_display}")
    else:
        st.write("None")
    
    st.write("---")
    st.write("**🏪 Chemist Visits:**")
    chemist_names = dcr_data.get('chemist_names', [])
    if chemist_names:
        for name in chemist_names:
            st.write(f"• {name}")
    else:
        st.write("None")
    
    st.write("---")
    st.write("**🎁 Gifts:**")
    gifts = dcr_data.get('gifts', [])
    if gifts:
        total_gift_amount = sum(g['gift_amount'] for g in gifts)
        st.write(f"Total: ₹{total_gift_amount}")
        for gift in gifts:
            st.write(f"• Dr. {gift['doctor_name']}: {gift['gift_description']} (₹{gift['gift_amount']})")
    else:
        st.write("None")
    
    st.write("---")
    st.write("**💰 Expenses:**")
    st.write(f"🚗 KM Travelled: {dcr_data.get('km_travelled', 0)}")
    st.write(f"💰 Misc Expense: ₹{dcr_data.get('misc_expense', 0)}")
    if dcr_data.get('misc_expense_details'):
        st.write(f"📝 Details: {dcr_data['misc_expense_details']}")
    
    # Edit buttons
    st.write("---")
    st.write("**Need to edit?**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✏️ Edit Basic Info"):
            st.session_state.dcr_current_step = 1
            st.rerun()
    with col2:
        if st.button("✏️ Edit Visits"):
            st.session_state.dcr_current_step = 2
            st.rerun()
    with col3:
        if st.button("✏️ Edit Expenses"):
            st.session_state.dcr_current_step = 3
            st.rerun()
    
    # Final submit
    st.write("---")
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("✅ Final Submit", type="primary"):
            submit_dcr_final(dcr_id, get_current_user_id())
            st.session_state.dcr_submit_done = True
            st.rerun()
    with col2:
        if st.button("❌ Cancel / Delete this DCR"):
            if st.session_state.get("dcr_delete_confirm"):
                delete_dcr_soft(dcr_id, get_current_user_id())
                st.session_state.dcr_report_id = None
                st.session_state.dcr_current_step = 0
                st.session_state.dcr_delete_confirm = False
                st.session_state.active_module = None
                st.success("DCR cancelled and deleted")
                st.rerun()
            else:
                st.session_state.dcr_delete_confirm = True
                st.warning("⚠️ Click again to confirm deletion")


def show_post_submit_screen():
    """Post-submission screen"""
    st.success("✅ DCR Submitted Successfully!")
    
    dcr_id = st.session_state.dcr_report_id
    
    st.write("---")
    st.write("**What would you like to do next?**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        import urllib.parse
        message = format_whatsapp_message(dcr_id)
        encoded = urllib.parse.quote(message)
        st.link_button(
            "📱 Share on WhatsApp",
            url=f"https://wa.me/?text={encoded}",
            use_container_width=True
        )
    
    with col2:
        if st.button("➕ New DCR", type="primary", use_container_width=True):
            st.session_state.dcr_report_id = None
            st.session_state.dcr_current_step = 0
            st.session_state.dcr_submit_done = False
            st.rerun()
    
    with col3:
        if st.button("🗑️ Delete This DCR", use_container_width=True):
            delete_dcr_soft(dcr_id, get_current_user_id())
            st.success("DCR deleted")
            st.session_state.dcr_report_id = None
            st.session_state.dcr_submit_done = False
            st.rerun()
    
    if st.button("🏠 Back to Home"):
        st.session_state.dcr_report_id = None
        st.session_state.dcr_submit_done = False
        st.session_state.dcr_current_step = 0
        st.session_state.dcr_new_report = False
        st.session_state.dcr_show_history = False
        st.session_state.active_module = None
        st.rerun()
# ======================================================
# ADMIN EXPENSE REPORT
# ======================================================

def show_expense_report():
    """Admin-only expense calculation report."""
    import urllib.parse
    import io
    from anchors.supabase_client import admin_supabase, safe_exec

    role = st.session_state.get("role", "user")
    if role != "admin":
        st.error("🔒 Only admin can access this section.")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_masters_mode = None
            st.rerun()
        return

    st.write("### 💰 Expense Calculation Report")

    if st.button("⬅️ Back to Home"):
        st.session_state.dcr_masters_mode = None
        st.rerun()

    st.write("---")

    # ── Filters ──────────────────────────────────────────────
    users = safe_exec(
        admin_supabase.table("users")
        .select("id, username")
        .eq("is_active", True)
        .order("username"),
        "Error loading users"
    )
    if not users:
        st.error("No users found.")
        return

    user_map = {u["id"]: u["username"] for u in users}

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_user_id = st.selectbox(
            "Select User *",
            options=list(user_map.keys()),
            format_func=lambda x: user_map.get(x, x),
            key="exp_user"
        )
    with col2:
        from_date = st.date_input(
            "From Date *",
            value=date.today().replace(day=1),
            key="exp_from_date"
        )
    with col3:
        to_date = st.date_input(
            "To Date *",
            value=date.today(),
            key="exp_to_date"
        )

    if st.button("📊 Generate Report", type="primary", use_container_width=True):
        st.session_state.exp_generate = True
        st.session_state.exp_user_id = selected_user_id
        st.session_state.exp_from = str(from_date)
        st.session_state.exp_to = str(to_date)
        st.rerun()

    if not st.session_state.get("exp_generate"):
        return

    # ── Fetch data ────────────────────────────────────────────
    uid   = st.session_state.exp_user_id
    f_dt  = st.session_state.exp_from
    t_dt  = st.session_state.exp_to
    uname = user_map.get(uid, "Unknown")

    reports = safe_exec(
        admin_supabase.table("dcr_reports")
        .select(
            "id, report_date, area_type, territory_ids, "
            "km_travelled, misc_expense, misc_expense_details, status"
        )
        .eq("user_id", uid)
        .eq("status", "submitted")
        .eq("is_deleted", False)
        .gte("report_date", f_dt)
        .lte("report_date", t_dt)
        .order("report_date"),
        "Error loading reports"
    )

    if not reports:
        st.warning(f"No submitted DCRs found for {uname} between {f_dt} and {t_dt}.")
        return

    # ── Enrich with territory names and visit counts ──────────
    territories_all = safe_exec(
        admin_supabase.table("territories").select("id, name"),
        "Error loading territories"
    )
    # Build map with string keys — Supabase returns jsonb UUIDs as strings
    terr_map = {str(t["id"]): t["name"] for t in territories_all}

    rows = []
    for r in reports:
        # Territory names — territory_ids is jsonb, may be list or None
        t_ids = r.get("territory_ids") or []
        if isinstance(t_ids, list) and t_ids:
            terr_names = ", ".join(
                terr_map.get(str(tid), str(tid)[:8])
                for tid in t_ids
            ) or "—"
        elif r.get("area_type") == "MEETING":
            terr_names = "Meeting"
        else:
            terr_names = "—"

        # Doctor visits + visited_with
        visits = safe_exec(
            admin_supabase.table("dcr_doctor_visits")
            .select("visited_with")
            .eq("dcr_report_id", r["id"]),
            "Error loading visits"
        )
        num_doctors = len(visits)

        # Gifts given on this date
        gifts = safe_exec(
            admin_supabase.table("dcr_gifts")
            .select("gift_amount")
            .eq("dcr_report_id", r["id"]),
            "Error loading gifts"
        )
        total_gift = sum(float(g.get("gift_amount") or 0) for g in gifts)

        # Collect unique "visited with" names
        visited_with_set = set()
        for v in visits:
            vw = v.get("visited_with", "")
            if vw and vw != "single":
                for vid in vw.split(","):
                    vid = vid.strip()
                    if vid and vid != "single":
                        visited_with_set.add(vid)

        # Resolve IDs to names
        if visited_with_set:
            mgr_rows = safe_exec(
                admin_supabase.table("users")
                .select("id, username")
                .in_("id", list(visited_with_set)),
                "Error loading managers"
            )
            name_map = {m["id"]: m["username"] for m in mgr_rows}
            visited_with_str = ", ".join(name_map.get(vid, vid) for vid in visited_with_set) or "Self"
        else:
            visited_with_str = "Self"

        rows.append({
            "Date":             r["report_date"],
            "Territories":      terr_names,
            "Visited With":     visited_with_str,
            "Doctors Visited":  num_doctors,
            "KM Travelled":     float(r.get("km_travelled") or 0),
            "Misc Expense (₹)": float(r.get("misc_expense") or 0),
            "Gifts Given (₹)":  total_gift,
        })

    import pandas as pd
    df = pd.DataFrame(rows)

    # Totals row
    totals = {
        "Date":             "TOTAL",
        "Territories":      "",
        "Visited With":     "",
        "Doctors Visited":  df["Doctors Visited"].sum(),
        "KM Travelled":     df["KM Travelled"].sum(),
        "Misc Expense (₹)": df["Misc Expense (₹)"].sum(),
        "Gifts Given (₹)":  df["Gifts Given (₹)"].sum(),
    }
    df_display = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)

    # ── Display ───────────────────────────────────────────────
    st.write(f"#### 📋 Expense Report — {uname} | {f_dt} to {t_dt}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.write("---")
    st.write(f"**Summary:** {len(rows)} working days | "
             f"Total KM: {df['KM Travelled'].sum():.1f} | "
             f"Total Expense: ₹{df['Misc Expense (₹)'].sum():.2f} | "
             f"Total Gifts: ₹{df['Gifts Given (₹)'].sum():.2f} | "
             f"Total Doctors: {int(df['Doctors Visited'].sum())}")

    # ── Export buttons ────────────────────────────────────────
    st.write("---")
    col_a, col_b, col_c = st.columns(3)

    # CSV
    with col_a:
        csv_data = df_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download CSV",
            data=csv_data,
            file_name=f"expense_{uname}_{f_dt}_{t_dt}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # PDF
    with col_b:
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors

            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                    leftMargin=30, rightMargin=30,
                                    topMargin=30, bottomMargin=30)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            elements.append(Paragraph(
                f"Expense Report — {uname} | {f_dt} to {t_dt}",
                styles["Heading2"]
            ))
            elements.append(Spacer(1, 10))

            # Table data
            headers = list(df_display.columns)
            data = [headers] + [list(row) for row in df_display.itertuples(index=False)]

            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#1a6b5a")),
                ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
                ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f0f0f0")]),
                ("BACKGROUND",  (0, -1), (-1, -1), colors.HexColor("#d4edda")),
                ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN",       (3, 1), (-1, -1), "RIGHT"),
                ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING",     (0, 0), (-1, -1), 5),
            ]))
            elements.append(t)
            doc.build(elements)
            pdf_bytes = buf.getvalue()

            st.download_button(
                "📄 Download PDF",
                data=pdf_bytes,
                file_name=f"expense_{uname}_{f_dt}_{t_dt}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except ImportError:
            st.warning("PDF export requires reportlab. Ask admin to install it.")

    # WhatsApp
    with col_c:
        wa_lines = [
            f"💰 *Expense Report*",
            f"👤 User: *{uname}*",
            f"📅 Period: {f_dt} to {t_dt}",
            f"─────────────────",
        ]
        for row in rows:
            wa_lines.append(
                f"📆 {row['Date']} | {row['Territories']} | "
                f"Docs: {row['Doctors Visited']} | "
                f"KM: {row['KM Travelled']} | "
                f"Exp: ₹{row['Misc Expense (₹)']} | "
                f"Gifts: ₹{row['Gifts Given (₹)']}"
            )
        wa_lines += [
            f"─────────────────",
            f"📊 Days: {len(rows)} | KM: {df['KM Travelled'].sum():.1f} | "
            f"Expense: ₹{df['Misc Expense (₹)'].sum():.2f} | "
            f"Gifts: ₹{df['Gifts Given (₹)'].sum():.2f} | "
            f"Doctors: {int(df['Doctors Visited'].sum())}"
        ]
        wa_msg = "\n".join(wa_lines)
        encoded = urllib.parse.quote(wa_msg)
        st.link_button(
            "📱 Share on WhatsApp",
            url=f"https://wa.me/?text={encoded}",
            use_container_width=True
        )
