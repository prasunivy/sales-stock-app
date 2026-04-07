"""
Doctors Master - CRUD Operations
Manage doctors within DCR module
"""

import streamlit as st
from modules.dcr.masters_database import (
    get_doctors_list,
    get_doctor_by_id,
    create_doctor,
    update_doctor,
    delete_doctor_soft,
    get_user_territories,
    get_stockists_by_territories,
    get_chemists_by_territories,
    get_all_users
)
from modules.dcr.dcr_helpers import get_current_user_id


def run_doctors_master():
    """
    Main entry point for Doctors Master
    """
    st.title("👨‍⚕️ Doctors Master")
    
    # Initialize state
    if "doctors_master_action" not in st.session_state:
        st.session_state.doctors_master_action = None
    if "selected_doctor_id" not in st.session_state:
        st.session_state.selected_doctor_id = None
    
    # Route
    action = st.session_state.doctors_master_action
    
    if action == "ADD":
        show_add_doctor_form()
    elif action == "EDIT":
        show_edit_doctor_form()
    else:
        show_doctors_list()


def show_doctors_list():
    """
    Show list of doctors with search and filters
    """
    current_user_id = get_current_user_id()
    role = st.session_state.get("role", "user")
    
    # Back button
    if st.button("⬅️ Back to DCR Home"):
        st.session_state.doctors_master_action = None
        st.session_state.selected_doctor_id = None
        st.session_state.dcr_masters_mode = None  
        st.session_state.dcr_current_step = 0
        st.rerun()
    
    st.write("---")
    
    # Admin: Select user
    selected_user_id = current_user_id
    if role == "admin":
        st.write("### Admin: Select User")
        users = get_all_users()
        
        user_options = {u['id']: u['username'] for u in users}
        selected_user_id = st.selectbox(
            "View doctors for user:",
            options=list(user_options.keys()),
            format_func=lambda x: user_options[x]
        )
        st.write("---")
    
    # Search and filters
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        search_query = st.text_input("🔍 Search doctors", placeholder="Doctor name...")
    
    with col2:
        user_territories = get_user_territories(selected_user_id)
        territory_filter = st.selectbox(
            "Filter by Territory",
            options=[None] + [t['id'] for t in user_territories],
            format_func=lambda x: "All Territories" if x is None else next((t['name'] for t in user_territories if t['id'] == x), x)
        )
    
    with col3:
        active_only = st.checkbox("Active only", value=True)
    
    # Add button — admin only
    role = st.session_state.get("role", "user")
    if role != "admin":
        st.info("ℹ️ Only admin can add or delete doctors. Please contact your admin.")
    else:
        if st.button("➕ Add New Doctor", type="primary"):
            st.session_state.doctors_master_action = "ADD"
            st.session_state.doctors_master_selected_user = selected_user_id
            st.rerun()

    st.write("---")
    
    # Get doctors
    doctors = get_doctors_list(
        user_id=selected_user_id,
        search=search_query,
        territory_id=territory_filter,
        active_only=active_only
    )
    
    st.write(f"### 📋 Doctors ({len(doctors)} found)")
    
    if not doctors:
        st.info("No doctors found. Click 'Add New Doctor' to create one.")
        return
    
    # Display doctors
    for doctor in doctors:
        with st.expander(f"Dr. {doctor['name']} | {doctor.get('specialization', 'N/A')}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**📞 Phone:** {doctor.get('phone', 'N/A')}")
                st.write(f"**🏥 Clinic:** {doctor.get('clinic_address', 'N/A')}")
                st.write(f"**📍 Territories:** {', '.join(doctor.get('territory_names', []))}")
                st.write(f"**🏪 Stockists:** {', '.join(doctor.get('stockist_names', []))}")
                st.write(f"**💊 Linked Chemists:** {len(doctor.get('chemist_ids', []))}")
            
            with col2:
                if st.button("✏️ Edit", key=f"edit_{doctor['id']}"):
                    st.session_state.doctors_master_action = "EDIT"
                    st.session_state.selected_doctor_id = doctor['id']
                    st.session_state.doctors_master_selected_user = selected_user_id
                    st.rerun()
                
                if role == "admin":
                    if st.button("🗑️ Delete", key=f"delete_{doctor['id']}"):
                        if st.session_state.get(f"confirm_delete_{doctor['id']}"):
                            delete_doctor_soft(doctor['id'], current_user_id)
                            st.success("Doctor deleted!")
                            st.rerun()
                        else:
                            st.session_state[f"confirm_delete_{doctor['id']}"] = True
                            st.warning("Click again to confirm")


def show_add_doctor_form():
    """
    Form to add new doctor — admin only
    """
    current_user_id = get_current_user_id()
    role = st.session_state.get("role", "user")

    # Guard: only admin can add doctors
    if role != "admin":
        st.warning("⚠️ Only admin can add doctors. Please contact your admin.")
        if st.button("⬅️ Back to List"):
            st.session_state.doctors_master_action = None
            st.session_state.selected_doctor_id = None
            st.rerun()
        return

    # Initialize form counter to prevent duplicate keys
    if "doctors_form_counter" not in st.session_state:
        st.session_state.doctors_form_counter = 0

    form_id = st.session_state.doctors_form_counter
    st.write("### ➕ Add New Doctor")

    selected_user_id = st.session_state.get("doctors_master_selected_user", current_user_id)

    # Back button
    if st.button("⬅️ Back to List"):
        st.session_state.doctors_master_action = None
        st.session_state.selected_doctor_id = None
        st.rerun()

    st.write("---")

    # Show which user this doctor is being created for
    users = get_all_users()
    user_options = {u['id']: u['username'] for u in users}
    st.info(f"Creating doctor for: **{user_options.get(selected_user_id, 'Unknown')}**")

    # Form
    with st.form(f"add_doctor_form_{form_id}"):
        # Basic info
        doctor_name = st.text_input("Doctor Name *", placeholder="Dr. John Doe")
        specialization = st.text_input("Specialization", placeholder="Cardiologist")
        phone = st.text_input("Phone", placeholder="+91 98XXXXXXXX")
        clinic_address = st.text_area("Clinic Address", placeholder="123 Main St, City")

        st.write("---")

        # Territories
        st.write("#### Territories *")
        user_territories = get_user_territories(selected_user_id)

        if not user_territories:
            st.error("No territories assigned to this user!")
            st.stop()

        territory_options = {t['id']: t['name'] for t in user_territories}
        selected_territories = st.multiselect(
            "Select territories:",
            options=list(territory_options.keys()),
            default=list(territory_options.keys()),
            format_func=lambda x: territory_options[x],
            key=f"terr_multi_{form_id}"
        )

        # Submit
        submitted = st.form_submit_button("💾 Save Doctor", type="primary")

    # Handle submission OUTSIDE form
    if submitted:
        if not doctor_name:
            st.error("Doctor name is required")
        elif not selected_territories:
            st.error("Please select at least one territory")
        else:
            try:
                new_doctor_id = create_doctor(
                    name=doctor_name,
                    specialization=specialization,
                    phone=phone,
                    clinic_address=clinic_address,
                    territory_ids=selected_territories,
                    stockist_ids=[],
                    chemist_ids=[],
                    created_by=current_user_id
                )
                st.success(f"✅ Doctor added successfully!")
                st.session_state.doctors_form_counter += 1
                st.session_state.doctors_master_action = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving doctor: {str(e)}")
def show_edit_doctor_form():
    """
    Form to edit existing doctor
    """
    st.write("### ✏️ Edit Doctor")
    
    doctor_id = st.session_state.selected_doctor_id
    current_user_id = get_current_user_id()
    
    # Back button
    if st.button("⬅️ Back to List"):
        st.session_state.doctors_master_action = None
        st.session_state.selected_doctor_id = None
        st.rerun()
    
    # Load doctor
    doctor = get_doctor_by_id(doctor_id)
    
    if not doctor:
        st.error("Doctor not found")
        return
    
    st.write("---")
    
    # Form (pre-filled)
    with st.form("edit_doctor_form"):
        doctor_name = st.text_input("Doctor Name *", value=doctor['name'])
        specialization = st.text_input("Specialization", value=doctor.get('specialization', ''))
        phone = st.text_input("Phone", value=doctor.get('phone', ''))
        clinic_address = st.text_area("Clinic Address", value=doctor.get('clinic_address', ''))
        
        st.write("---")
        st.write("#### Territories")
        st.info("Territory changes not allowed (has existing DCR visits)")
        for t_name in doctor.get('territory_names', []):
            st.write(f"✓ {t_name}")
        
        st.write("---")
        
        # Stockists (editable)
        st.write("#### Stockists")
        existing_stockist_ids = doctor.get('stockist_ids', [])
        territory_ids = doctor.get('territory_ids', [])
        stockists = get_stockists_by_territories(territory_ids)
        selected_stockists = []
        
        for s in stockists:
            default = s['id'] in existing_stockist_ids
            if st.checkbox(s['name'], value=default, key=f"stock_{s['id']}"):
                selected_stockists.append(s['id'])
        
        st.write("---")
        
        # Chemists (editable)
        st.write("#### Linked Chemists")
        existing_chemist_ids = doctor.get('chemist_ids', [])
        chemists = get_chemists_by_territories(territory_ids)
        selected_chemists = []
        
        for c in chemists:
            default = c['id'] in existing_chemist_ids
            if st.checkbox(f"{c['name']} ({c['shop_name']})", value=default, key=f"chem_{c['id']}"):
                selected_chemists.append(c['id'])
        
        # Submit
        submitted = st.form_submit_button("💾 Update Doctor", type="primary")
        
        if submitted:
            if not doctor_name:
                st.error("Doctor name is required")
            else:
                try:
                    update_doctor(
                        doctor_id=doctor_id,
                        name=doctor_name,
                        specialization=specialization,
                        phone=phone,
                        clinic_address=clinic_address,
                        stockist_ids=selected_stockists,
                        chemist_ids=selected_chemists,
                        updated_by=current_user_id
                    )
                    st.success("✅ Doctor updated successfully!")
                    st.session_state.doctors_master_action = None
                    st.session_state.selected_doctor_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error updating doctor: {str(e)}")
