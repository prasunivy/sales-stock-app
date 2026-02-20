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
from modules.dcr.tour_programme import run_tour_programme 


def run_dcr():
    """Main entry point for DCR module"""
    init_dcr_session_state()
    
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

    if st.session_state.get("dcr_masters_mode") == "TOUR":
        run_tour_programme()
        return
    
    
    # Route based on state
    if st.session_state.get("dcr_submit_done"):
        show_post_submit_screen()
    elif st.session_state.get("dcr_current_step", 0) >= 1:
        show_dcr_flow()
    else:
        show_home_screen()

def show_home_screen():
    """Home screen with DCR options and Masters"""
    st.write("### What would you like to do?")
    
    # DCR Actions
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("➕ New Daily Report", type="primary", use_container_width=True, key="btn_new_dcr"):
            # Clear any existing DCR state
            st.session_state.dcr_current_step = 1
            st.session_state.dcr_report_id = None
            st.session_state.dcr_submit_done = False
            st.session_state.dcr_home_action = None
            st.rerun()
    
    with col2:
        if st.button("📅 View My Reports", use_container_width=True, key="btn_view_reports"):
            st.session_state.dcr_home_action = "HISTORY"
            st.rerun()
    
    # Tour Programme
    st.write("---")
    st.write("### 📅 Tour Planning")
    
    if st.button("📅 Tour Programme", use_container_width=True, key="btn_tour_programme"):
        st.session_state.dcr_masters_mode = "TOUR"
        st.rerun()
    
    # Masters Section
    st.write("---")
    st.write("### 📚 Masters (Manage Data)")
    
    col3, col4 = st.columns(2)
    
    with col3:
        if st.button("👨‍⚕️ Doctors Master", use_container_width=True, key="btn_doctors_master"):
            st.session_state.dcr_masters_mode = "DOCTORS"
            st.rerun()
    
    with col4:
        if st.button("🏪 Chemists Master", use_container_width=True, key="btn_chemists_master"):
            st.session_state.dcr_masters_mode = "CHEMISTS"
            st.rerun()
    
    # Handle history view if requested
    if st.session_state.get("dcr_home_action") == "HISTORY":
        st.write("---")
        show_monthly_history()


def show_monthly_history():
    """Show monthly DCR history"""
    st.write("---")
    st.write("### 📅 My DCR History")
    
    user_id = get_current_user_id()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        selected_month = st.selectbox(
            "Month",
            options=list(range(1, 13)),
            format_func=lambda x: datetime(2000, x, 1).strftime("%B"),
            index=datetime.now().month - 1
        )
    
    with col2:
        selected_year = st.selectbox(
            "Year",
            options=list(range(2020, 2031)),
            index=datetime.now().year - 2020
        )
    
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    reports = load_dcr_monthly_reports(user_id, selected_year, selected_month)
    
    if not reports:
        st.info(f"No reports found for {datetime(2000, selected_month, 1).strftime('%B')} {selected_year}")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_current_step = 0
            st.rerun()
        return
    
    submitted = [r for r in reports if r['status'] == 'submitted']
    
    if submitted:
        st.write(f"**✅ Submitted ({len(submitted)} days)**")
        for report in submitted:
            with st.expander(f"{report['report_date']} - {report['area_type']}"):
                st.write(f"📍 Doctors: {report.get('doctor_count', 0)}")
                st.write(f"🏪 Chemists: {report.get('chemist_count', 0)}")
                st.write(f"🎁 Gifts: {report.get('gift_count', 0)}")
                st.write(f"🚗 KM: {report.get('km_travelled', 0)}")
                st.write(f"💰 Expenses: ₹{report.get('misc_expense', 0)}")
    
    if st.button("⬅️ Back to Home"):
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
        # Creating new DCR - check for duplicates
        if check_duplicate_dcr(selected_user_id, report_date):
            st.error("❌ DCR already exists for this date")
            if st.button("⬅️ Back to Home"):
                st.session_state.dcr_current_step = 0
                st.session_state.active_module = None
                st.rerun()
            return
    else:
        # Editing existing DCR - allow it
        # But prevent changing to a date that has another DCR
        existing_dcr = get_dcr_by_id(st.session_state.dcr_report_id)
        if existing_dcr and str(existing_dcr.get('report_date')) != str(report_date):
            # User is trying to change the date
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
            # Clear ALL DCR state
            st.session_state.dcr_current_step = 0
            st.session_state.dcr_report_id = None
            st.session_state.engine_stage = None  
            st.session_state.active_module = None
            st.rerun()

def show_stage_2_visits():
    """Stage 2: Doctor Visits + Chemist Visits + Gifts"""
    st.write("### Stage 2/4: Visits & Gifts")
    
    dcr_id = st.session_state.dcr_report_id
    territory_ids = st.session_state.dcr_territory_ids
    
    dcr_data = get_dcr_by_id(dcr_id)
    # Initialize variables at the top to avoid UnboundLocalError
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
        # Show existing visits
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
        
        # Get already added doctor IDs to prevent duplicates
        added_doctor_ids = [v['doctor_id'] for v in existing_visits]
        available_doctors = [d for d in doctors if d['id'] not in added_doctor_ids]
        
        if not available_doctors:
            st.info("✅ All doctors in this territory have been added")
        else:
            # Add new doctor form
            with st.form("add_doctor_form"):
                st.write("**Add Doctor Visit**")
                
                # Add placeholder option
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
                
                # Add "single" option + managers
                visited_with_options = ["single"] + [m['id'] for m in managers]
                visited_with = st.multiselect(
                    "Visited With * (Required)",
                    options=visited_with_options,
                    format_func=lambda x: "Self (Alone)" if x == "single" else next((m['username'] for m in managers if m['id'] == x), x),
                    help="Select 'Self' if alone, or select who accompanied you"
                )
                
                submit_doctor = st.form_submit_button("➕ Add Doctor")
                
                if submit_doctor:
                    # Validation
                    if selected_doctor is None:
                        st.error("❌ Please select a doctor")
                    elif not selected_products:
                        st.error("❌ Please select at least one product")
                    elif not visited_with:
                        st.error("❌ Please select who you visited with (required)")
                    else:
                        # All validations passed
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
        # Get existing chemist IDs safely
        existing_chemist_ids = dcr_data.get('chemist_ids', [])
        
        # Ensure it's a list
        if not isinstance(existing_chemist_ids, list):
            existing_chemist_ids = []
        
        # Filter existing IDs to only include valid ones
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
    if existing_gifts:
        st.write(f"**Added: {len(existing_gifts)} gift(s)**")
        for idx, gift in enumerate(existing_gifts):
            with st.expander(f"Dr. {gift['doctor_name']} - ₹{gift['gift_amount']}"):
                st.write(f"**Gift:** {gift['gift_description']}")
                if st.button(f"🗑️ Remove", key=f"remove_gift_{idx}"):
                    remove_gift(gift['id'])
                    st.rerun()
    
    # Add gift form
    if existing_visits:
        # Get doctors who already have gifts
        doctors_with_gifts = [g['doctor_id'] for g in existing_gifts]
        available_gift_doctors = [v['doctor_id'] for v in existing_visits if v['doctor_id'] not in doctors_with_gifts]
        
        if not available_gift_doctors:
            st.info("✅ All visited doctors already have gifts recorded")
        else:
            with st.form("add_gift_form"):
                st.write("**Add Gift**")
                
                # Add placeholder
                gift_doctor_options = [None] + available_gift_doctors
                
                gift_doctor = st.selectbox(
                    "Select Doctor *",
                    options=gift_doctor_options,
                    format_func=lambda x: "-- Select a doctor --" if x is None else next((v['doctor_name'] for v in existing_visits if v['doctor_id'] == x), "Unknown"),
                    index=0
                )
                
                gift_description = st.text_input(
                    "Gift Description *",
                    placeholder="e.g., Medical Books, Calendar, Pen Set",
                    help="Enter what gift was given"
                )
                
                gift_amount = st.number_input(
                    "Gift Amount (₹) *",
                    min_value=0.0,
                    step=10.0,
                    help="Enter the value of the gift"
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
    
    # KM travelled
    km_travelled = st.number_input(
        "🚗 KM Travelled",
        min_value=0.0,
        step=1.0,
        value=float(dcr_data.get('km_travelled', 0))
    )
    
    # Misc expense
    misc_expense = st.number_input(
        "💰 Miscellaneous Expense (₹)",
        min_value=0.0,
        step=10.0,
        value=float(dcr_data.get('misc_expense', 0))
    )
    
    # Details
    misc_expense_details = st.text_area(
        "📝 Expense Details (Optional)",
        value=dcr_data.get('misc_expense_details', ''),
        placeholder="e.g., Parking, Toll, Food"
    )
    
    # Preview
    st.write("---")
    st.write("**Preview:**")
    st.write(f"🚗 KM: {km_travelled}")
    st.write(f"💰 Misc Expense: ₹{misc_expense}")
    if misc_expense_details:
        st.write(f"📝 Details: {misc_expense_details}")
    
    # Navigation
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
    
    # Safety check
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
    
    # Check if data is valid
    if not dcr_data or not dcr_data.get('report_date'):
        st.error("❌ DCR data is incomplete or corrupted")
        if st.button("🏠 Back to Home"):
            st.session_state.dcr_report_id = None
            st.session_state.dcr_current_step = 0
            st.session_state.active_module = None
            st.rerun()
        return
    
    # Header
    st.write("---")
    st.write("#### 📋 DCR Summary")
    st.write(f"**Date:** {dcr_data['report_date']}")
    st.write(f"**Area:** {dcr_data['area_type']}")
    
    # Territories
    if dcr_data.get('territory_names'):
        st.write(f"**Territories:** {', '.join(dcr_data['territory_names'])}")
    
    # Doctor visits
    st.write("---")
    st.write("**👨‍⚕️ Doctor Visits:**")
    doctor_visits = dcr_data.get('doctor_visits', [])
    if doctor_visits:
        for visit in doctor_visits:
            # Resolve visited_with to names
            visited_with_raw = visit.get('visited_with', 'single')
            if visited_with_raw == 'single' or not visited_with_raw:
                visited_with_display = "Self (Alone)"
            else:
                # It's a comma-separated list of IDs
                ids = visited_with_raw.split(',')
                # Resolve to names
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
    
    # Chemist visits
    st.write("---")
    st.write("**🏪 Chemist Visits:**")
    chemist_names = dcr_data.get('chemist_names', [])
    if chemist_names:
        for name in chemist_names:
            st.write(f"• {name}")
    else:
        st.write("None")
    
    # Gifts
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
    
    # Expenses
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
        if st.button("❌ Cancel"):
            if st.session_state.get("dcr_delete_confirm"):
                # Actually delete
                delete_dcr_soft(dcr_id, get_current_user_id())
                # Clear state
                st.session_state.dcr_report_id = None
                st.session_state.dcr_current_step = 0
                st.session_state.dcr_delete_confirm = False
                st.session_state.active_module = None
                st.success("DCR cancelled and deleted")
                st.rerun()
            else:
                # Show confirmation
                st.session_state.dcr_delete_confirm = True
                st.warning("⚠️ Click again to confirm cancellation")


def show_post_submit_screen():
    """Post-submission screen"""
    st.success("✅ DCR Submitted Successfully!")
    
    dcr_id = st.session_state.dcr_report_id
    
    st.write("---")
    st.write("**What would you like to do next?**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📱 Share on WhatsApp", use_container_width=True):
            message = format_whatsapp_message(dcr_id)
            st.code(message, language=None)
            st.write("Copy the message above and share on WhatsApp")
    
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
        st.session_state.active_module = None
        st.rerun()
