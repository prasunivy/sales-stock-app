"""
DCR Main Module - Daily Call Report
Entry point for the DCR workflow
Handles 4-stage flow: Header → Visits → Expenses → Preview
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


def run_dcr():
    """
    Main entry point for DCR module
    Called from app.py when user clicks "Daily Call Report" in sidebar
    """
    
    # Initialize session state
    init_dcr_session_state()
    
    # Show title FIRST (before checking auth)
    st.title("📞 Daily Call Report")
    
    # Check authentication
    try:
        user_id = get_current_user_id()
        role = st.session_state.get("role", "user")
    except Exception as e:
        st.error(f"❌ Authentication Error: {str(e)}")
        st.info("**Debug Info:**")
        st.write(f"- auth_user in session: {st.session_state.get('auth_user') is not None}")
        st.write(f"- role in session: {st.session_state.get('role')}")
        st.write(f"- Available keys: {list(st.session_state.keys())}")
        st.stop()
    
    # Route based on state
    if st.session_state.get("dcr_submit_done"):
        show_post_submit_screen()
    elif st.session_state.get("dcr_report_id"):
        show_dcr_flow()
    else:
        show_home_screen()


def show_home_screen():
    """
    Home screen with options: New DCR or View History
    """
    st.write("### What would you like to do?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("➕ New Daily Report", type="primary", use_container_width=True):
            st.session_state.dcr_home_action = "NEW"
            st.rerun()
    
    with col2:
        if st.button("📅 View My Reports", use_container_width=True):
            st.session_state.dcr_home_action = "HISTORY"
            st.rerun()
    
    # Handle action
    if st.session_state.get("dcr_home_action") == "NEW":
        st.session_state.dcr_home_action = None
        st.session_state.dcr_current_step = 1
        st.rerun()
    
    elif st.session_state.get("dcr_home_action") == "HISTORY":
        show_monthly_history()


def show_monthly_history():
    """
    Show monthly calendar of submitted/draft DCRs
    """
    st.write("---")
    st.write("### 📅 My DCR History")
    
    user_id = get_current_user_id()
    
    # Month/Year selector
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
    
    # Load reports
    reports = load_dcr_monthly_reports(user_id, selected_year, selected_month)
    
    if not reports:
        st.info(f"No reports found for {datetime(2000, selected_month, 1).strftime('%B')} {selected_year}")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_home_action = None
            st.rerun()
        return
    
    # Group by status
    submitted = [r for r in reports if r['status'] == 'submitted']
    drafts = [r for r in reports if r['status'] == 'draft']
    
    # Show submitted
    if submitted:
        st.write(f"**✅ Submitted ({len(submitted)} days)**")
        for report in submitted:
            with st.expander(f"{report['report_date']} - {report['area_type']}"):
                st.write(f"📍 Doctors: {report.get('doctor_count', 0)}")
                st.write(f"🏪 Chemists: {report.get('chemist_count', 0)}")
                st.write(f"🎁 Gifts: {report.get('gift_count', 0)}")
                st.write(f"🚗 KM: {report.get('km_travelled', 0)}")
                st.write(f"💰 Expenses: ₹{report.get('misc_expense', 0)}")
                if st.button(f"👁️ View", key=f"view_{report['id']}"):
                    st.info("View feature coming soon")
    
    # Show drafts
    if drafts:
        st.write(f"**⚠️ Drafts ({len(drafts)} incomplete)**")
        for report in drafts:
            with st.expander(f"{report['report_date']} - Step {report['current_step']}/4"):
                st.write(f"📍 Area: {report['area_type']}")
                st.write(f"⏰ Last saved: {report['updated_at']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"▶️ Resume", key=f"resume_{report['id']}"):
                        # Load draft into session
                        st.session_state.dcr_report_id = report['id']
                        st.session_state.dcr_current_step = report['current_step']
                        st.session_state.dcr_user_id = report['user_id']
                        st.session_state.dcr_report_date = report['report_date']
                        st.session_state.dcr_area_type = report['area_type']
                        st.rerun()
                
                with col2:
                    if st.button(f"🗑️ Delete", key=f"delete_{report['id']}"):
                        delete_dcr_soft(report['id'], get_current_user_id())
                        st.success("Draft deleted")
                        st.rerun()
    
    if st.button("⬅️ Back to Home"):
        st.session_state.dcr_home_action = None
        st.rerun()


def show_dcr_flow():
    """
    Main DCR workflow - routes to appropriate stage
    """
    step = st.session_state.dcr_current_step
    
    if step == 1:
        show_stage_1_header()
    elif step == 2:
        show_stage_2_visits()
    elif step == 3:
        show_stage_3_expenses()
    elif step == 4:
        show_stage_4_preview()


def show_stage_1_header():
    """
    Stage 1: Header + Territory Selection
    Collects: Date, Area Type, Territories
    """
    st.write("### Stage 1/4: Basic Information")
    
    role = st.session_state.get("role")
    
    # Get current user ID
    try:
        current_user_id = get_current_user_id()
    except:
        st.error("Unable to get user ID. Please refresh and try again.")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_home_action = None
            st.rerun()
        return
    
    # User selection (admin only)
    if role == "admin":
        st.write("**Admin Mode:** Creating DCR for user")
        selected_user_id = current_user_id  # For now, admin creates for themselves
    else:
        selected_user_id = current_user_id
    
    # Date picker
    report_date = st.date_input(
        "Report Date",
        value=date.today(),
        max_value=date.today(),
        help="Cannot select future dates"
    )
    
    # Validate date
    if report_date > date.today():
        st.error("❌ Cannot create DCR for future date")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_home_action = None
            st.rerun()
        return
    
    # Check duplicate
    if check_duplicate_dcr(selected_user_id, report_date):
        st.error("❌ DCR already exists for this date")
        if st.button("View Existing DCR"):
            st.info("View existing DCR feature coming soon")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_home_action = None
            st.rerun()
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
    
    # Territory selection (skip if MEETING)
    selected_territories = []
    if area_type != "MEETING":
        st.write("**Select Territories**")
        
        try:
            user_territories = get_user_territories(selected_user_id)
        except Exception as e:
            st.error(f"Error loading territories: {str(e)}")
            user_territories = []
        
        if not user_territories:
            st.warning("⚠️ No territories assigned to you.")
            st.info("**For testing:** You can still proceed by selecting MEETING area type, which doesn't require territories.")
            
            if st.button("⬅️ Back to Home"):
                st.session_state.dcr_home_action = None
                st.rerun()
            return
        
        selected_territories = st.multiselect(
            "Territories worked today",
            options=[t['id'] for t in user_territories],
            format_func=lambda x: next(t['name'] for t in user_territories if t['id'] == x),
            help="You can select multiple territories"
        )
        
        if not selected_territories:
            st.warning("⚠️ Please select at least one territory")
            if st.button("⬅️ Back to Home"):
                st.session_state.dcr_home_action = None
                st.rerun()
            return
    
    # Preview
    st.write("---")
    st.write("**Preview:**")
    st.write(f"📅 Date: {report_date}")
    st.write(f"📍 Area: {area_type}")
    if selected_territories:
        territory_names = [next(t['name'] for t in get_user_territories(selected_user_id) if t['id'] == tid) 
                          for tid in selected_territories]
        st.write(f"🗺️ Territories: {', '.join(territory_names)}")
    
    # Save & Next
    st.write("---")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("💾 Save & Next", type="primary", use_container_width=True):
            try:
                # Create or update DCR
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
                
                # Store in session
                st.session_state.dcr_user_id = selected_user_id
                st.session_state.dcr_report_date = report_date
                st.session_state.dcr_area_type = area_type
                st.session_state.dcr_territory_ids = selected_territories
                
                # Advance to next stage
                if area_type == "MEETING":
                    st.session_state.dcr_current_step = 3  # Skip visits, go to expenses
                else:
                    st.session_state.dcr_current_step = 2
                
                st.success("✅ Saved! Moving to next stage...")
                st.rerun()
            
            except Exception as e:
                st.error(f"❌ Error saving DCR: {str(e)}")
    
    with col2:
        if st.button("🏠 Back to Home", use_container_width=True):
            st.session_state.dcr_home_action = None
            st.session_state.dcr_report_id = None
            st.session_state.dcr_current_step = 1
            st.rerun()


def show_stage_2_visits():
    """
    Stage 2: Doctor Visits + Chemist Visits + Gifts
    All visit data collected here
    """
    st.write("### Stage 2/4: Visits & Gifts")
    
    dcr_id = st.session_state.dcr_report_id
    territory_ids = st.session_state.dcr_territory_ids
    
    # Load existing data
    dcr_data = get_dcr_by_id(dcr_id)
    
    # ========================================
    # DOCTORS SECTION
    # ========================================
    st.write("---")
    st.write("#### 👨‍⚕️ Doctor Visits")
    
    # Get doctors for selected territories
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
                    st.write(f"Products: {', '.join(visit['product_names'])}")
                    st.write(f"Visited with: {visit.get('visited_with', 'Single')}")
                    if st.button(f"🗑️ Remove", key=f"remove_doc_{idx}"):
                        remove_doctor_visit(visit['id'])
                        st.rerun()
        
        # Add new doctor form
        with st.form("add_doctor_form"):
            st.write("**Add Doctor Visit**")
            
            selected_doctor = st.selectbox(
                "Select Doctor",
                options=[d['id'] for d in doctors],
                format_func=lambda x: next(d['name'] for d in doctors if d['id'] == x)
            )
            
            selected_products = st.multiselect(
                "Products Promoted",
                options=[p['id'] for p in products],
                format_func=lambda x: next(p['name'] for p in products if p['id'] == x)
            )
            
            visited_with = st.multiselect(
                "Visited With (Optional)",
                options=[m['id'] for m in managers] + ["single"],
                format_func=lambda x: "Single" if x == "single" else next(m['username'] for m in managers if m['id'] == x)
            )
            
            if st.form_submit_button("➕ Add Doctor"):
                if not selected_products:
                    st.error("Please select at least one product")
                else:
                    save_doctor_visit(
                        dcr_id=dcr_id,
                        doctor_id=selected_doctor,
                        product_ids=selected_products,
                        visited_with=",".join(visited_with) if visited_with else "single"
                    )
                    st.success("Doctor visit added!")
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
        # Chemist multiselect
        existing_chemist_ids = dcr_data.get('chemist_ids', [])
        
        selected_chemists = st.multiselect(
            "Select Chemists Visited",
            options=[c['id'] for c in chemists],
            format_func=lambda x: next(c['name'] for c in chemists if c['id'] == x),
            default=existing_chemist_ids
        )
        
        if st.button("💾 Save Chemists"):
            save_chemist_visits(dcr_id, selected_chemists)
            st.success("Chemist visits saved!")
            st.rerun()
    
    # ========================================
    # GIFTS SECTION
    # ========================================
    st.write("---")
    st.write("#### 🎁 Gifts (Optional)")
    
    # Show existing gifts
    existing_gifts = dcr_data.get('gifts', [])
    if existing_gifts:
        st.write(f"**Added: {len(existing_gifts)} gift(s)**")
        for idx, gift in enumerate(existing_gifts):
            with st.expander(f"Dr. {gift['doctor_name']} - ₹{gift['gift_amount']}"):
                st.write(f"Gift: {gift['gift_description']}")
                if st.button(f"🗑️ Remove", key=f"remove_gift_{idx}"):
                    remove_gift(gift['id'])
                    st.rerun()
    
    # Add gift form
    if existing_visits:  # Only show if doctors added
        with st.form("add_gift_form"):
            st.write("**Add Gift**")
            
            gift_doctor = st.selectbox(
                "Select Doctor",
                options=[v['doctor_id'] for v in existing_visits],
                format_func=lambda x: next(v['doctor_name'] for v in existing_visits if v['doctor_id'] == x)
            )
            
            gift_description = st.text_input("Gift Description")
            gift_amount = st.number_input("Gift Amount (₹)", min_value=0.0, step=10.0)
            
            if st.form_submit_button("➕ Add Gift"):
                if gift_amount <= 0:
                    st.error("Gift amount must be greater than zero")
                elif not gift_description:
                    st.error("Please enter gift description")
                else:
                    save_gift(dcr_id, gift_doctor, gift_description, gift_amount)
                    st.success("Gift added!")
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
    """
    Stage 3: Expenses
    Collects: KM travelled, Misc expenses
    """
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
    """
    Stage 4: Preview & Submit
    Shows complete DCR summary with inline edit
    """
    st.write("### Stage 4/4: Preview & Submit")
    
    dcr_id = st.session_state.dcr_report_id
    dcr_data = get_dcr_by_id(dcr_id)
    
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
            st.write(f"• Dr. {visit['doctor_name']}")
            st.write(f"  Products: {', '.join(visit['product_names'])}")
            st.write(f"  With: {visit.get('visited_with', 'Single')}")
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
            if st.confirm("Discard this DCR?"):
                delete_dcr_soft(dcr_id, get_current_user_id())
                st.session_state.dcr_report_id = None
                st.session_state.dcr_current_step = 1
                st.rerun()


def show_post_submit_screen():
    """
    Post-submission screen with WhatsApp/New/Delete options
    """
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
            # Clear session
            st.session_state.dcr_report_id = None
            st.session_state.dcr_current_step = 1
            st.session_state.dcr_submit_done = False
            st.rerun()
    
    with col3:
        if st.button("🗑️ Delete This DCR", use_container_width=True):
            if st.session_state.get("dcr_delete_confirm"):
                delete_dcr_soft(dcr_id, get_current_user_id())
                st.success("DCR deleted")
                st.session_state.dcr_report_id = None
                st.session_state.dcr_submit_done = False
                st.session_state.dcr_delete_confirm = False
                st.rerun()
            else:
                st.session_state.dcr_delete_confirm = True
                st.warning("Click again to confirm deletion")
                st.rerun()
    
    if st.button("🏠 Back to Home"):
        st.session_state.dcr_report_id = None
        st.session_state.dcr_submit_done = False
        st.session_state.dcr_delete_confirm = False
        st.rerun()
