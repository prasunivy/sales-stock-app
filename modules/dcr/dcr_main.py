"""
DCR Main Module - Daily Call Report
Entry point for the DCR workflow
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
    """Main entry point for DCR module"""
    init_dcr_session_state()
    
    st.title("📞 Daily Call Report")
    
    try:
        user_id = get_current_user_id()
        role = st.session_state.get("role", "user")
    except Exception as e:
        st.error(f"❌ Authentication Error: {str(e)}")
        st.stop()
    
    # Check current state
    if st.session_state.get("dcr_current_step", 0) >= 1:
        show_dcr_flow()
    else:
        show_home_screen()


def show_home_screen():
    """Home screen"""
    st.write("### What would you like to do?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("➕ New Daily Report", type="primary", use_container_width=True):
            st.session_state.dcr_current_step = 1
            st.rerun()
    
    with col2:
        if st.button("📅 View My Reports", use_container_width=True):
            st.info("History feature coming soon")


def show_dcr_flow():
    """Route to appropriate stage"""
    step = st.session_state.get("dcr_current_step", 1)
    
    if step == 1:
        show_stage_1_header()
    else:
        st.info(f"Stage {step} coming soon")
        if st.button("⬅️ Back"):
            st.session_state.dcr_current_step = 0
            st.rerun()


def show_stage_1_header():
    """Stage 1: Basic Information"""
    st.write("### Stage 1/4: Basic Information")
    
    try:
        current_user_id = get_current_user_id()
    except:
        st.error("Unable to get user ID")
        if st.button("⬅️ Back to Home"):
            st.session_state.dcr_current_step = 0
            st.session_state.active_module = None
            st.rerun()
        return
    
    # Date picker
    report_date = st.date_input(
        "Report Date",
        value=date.today(),
        max_value=date.today()
    )
    
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
        
        try:
            user_territories = get_user_territories(current_user_id)
            
            st.info(f"DEBUG: Found {len(user_territories)} territories")
            if user_territories:
                for t in user_territories:
                    st.write(f"  - {t.get('name', 'Unknown')} (ID: {t.get('id', 'N/A')})")
            
        except Exception as e:
            st.error(f"Error loading territories: {str(e)}")
            user_territories = []
        
        if not user_territories:
            st.warning("⚠️ No territories assigned to you.")
            st.info("**For testing:** You can still proceed by selecting MEETING area type.")
            if st.button("⬅️ Back to Home"):
                st.session_state.dcr_current_step = 0
                st.session_state.active_module = None
                st.rerun()
            return
        
        selected_territories = st.multiselect(
            "Territories worked today",
            options=[t['id'] for t in user_territories],
            format_func=lambda x: next((t['name'] for t in user_territories if t['id'] == x), x)
        )
        
        if not selected_territories:
            st.warning("⚠️ Please select at least one territory")
    
    # Buttons
    st.write("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Save & Next", type="primary", use_container_width=True):
            st.info("Stage 2 coming soon - Full implementation in progress")
    
    with col2:
        if st.button("🏠 Back to Home", use_container_width=True):
            st.session_state.dcr_current_step = 0
            st.session_state.active_module = None
            st.rerun()
