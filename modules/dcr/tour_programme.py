"""
Tour Programme Module
Plan and manage daily tour programmes
"""

import streamlit as st
from datetime import date, datetime, timedelta
from modules.dcr.tour_database import (
    get_tour_programmes_list,
    get_tour_by_id,
    create_tour_programme,
    update_tour_programme,
    delete_tour_programme,
    get_doctors_by_territories,
    get_chemists_by_territories
)
from modules.dcr.dcr_database import get_user_territories
from modules.dcr.dcr_helpers import get_current_user_id


def run_tour_programme():
    """
    Main entry point for tour programme module
    """
    st.title("📅 Tour Programme")
    
    # Initialize state
    if "tour_action" not in st.session_state:
        st.session_state.tour_action = None
    if "selected_tour_id" not in st.session_state:
        st.session_state.selected_tour_id = None
    if "create_another" not in st.session_state:
        st.session_state.create_another = False
    
    # Route
    action = st.session_state.tour_action
    
    if action == "CREATE":
        show_create_tour_form()
    elif action == "EDIT":
        show_edit_tour_form()
    elif action == "VIEW":
        show_view_tour()
    elif action == "APPROVE":
        show_approve_tour()
    elif action == "REJECT":
        show_reject_tour()
    else:
        show_tour_list()


def show_tour_list():
    """
    List all tour programmes with filters
    """
    current_user_id = get_current_user_id()
    role = st.session_state.get("role", "user")
    
    # Back button
    if st.button("⬅️ Back to DCR Home"):
        st.session_state.tour_action = None
        st.session_state.dcr_masters_mode = None
        st.session_state.dcr_current_step = 0
        st.rerun()
    
    st.write("---")
    
    # Admin: Select user to view tours for
    selected_user_id = current_user_id
    if role == "admin":
        st.write("### 👤 Admin: View Tours For")
        
        from modules.dcr.masters_database import get_all_users
        users = get_all_users()
        
        user_options = {u['id']: u['username'] for u in users}
        user_options['all'] = 'All Users'
        
        view_mode = st.selectbox(
            "Select user:",
            options=['all'] + list(user_options.keys())[:-1],  # 'all' first, then users
            format_func=lambda x: user_options[x]
        )
        
        if view_mode != 'all':
            selected_user_id = view_mode
        
        st.write("---")
    
    # Filters and search
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search = st.text_input("🔍 Search notes", placeholder="Search...")
    
    with col2:
        status_filter = st.selectbox(
            "Filter by Status",
            options=[None, "draft", "pending", "approved", "rejected"],
            format_func=lambda x: "All Status" if x is None else x.upper()
        )
    
    with col3:
        if st.button("➕ Create Tour", type="primary"):
            st.session_state.pop("tour_create_selected_user", None)
            st.session_state.pop("tour_create_territories", None)
            st.session_state.tour_form_counter = 0
            st.session_state.tour_action = "CREATE"
            st.session_state.create_another = False
            st.rerun()
    
    st.write("---")
    
    # Get tours
    if role == "admin" and view_mode == 'all':
        # Admin viewing all users - need custom query
        from modules.dcr.tour_database import get_all_tour_programmes_admin
        tours = get_all_tour_programmes_admin(status_filter, search)
    else:
        tours = get_tour_programmes_list(selected_user_id, status_filter, search)
    
    st.write(f"### 📋 Tour Programmes ({len(tours)} found)")
    
    if not tours:
        st.info("No tour programmes found. Click 'Create Tour' to start planning!")
        return
    
    # Display tours
    for tour in tours:
        status_emoji = {
            "draft": "📝",
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌"
        }.get(tour['status'], "📝")
        
        with st.expander(f"{status_emoji} {tour['tour_date']} | {', '.join(tour['territory_names'][:2])} | {tour['status'].upper()}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**📅 Date:** {tour['tour_date']}")
                
                # Show user if admin
                if role == "admin":
                    from modules.dcr.masters_database import get_all_users
                    users = get_all_users()
                    user_dict = {u['id']: u['username'] for u in users}
                    tour_username = user_dict.get(tour.get('user_id'), 'Unknown')
                    st.write(f"**👤 User:** {tour_username}")
                
                st.write(f"**🗺️ Territories:** {', '.join(tour['territory_names'])}")
                st.write(f"**👥 Worked With:** {tour['worked_with_type'].replace('_', ' ').title()}")
                st.write(f"**👨‍⚕️ Doctors:** {tour['doctor_count']}")
                st.write(f"**🏪 Chemists:** {tour['chemist_count']}")
                
                if tour.get('notes'):
                    st.write(f"**📝 Notes:** {tour['notes']}")
                
                # Approval info
                if tour['status'] in ['approved', 'rejected']:
                    st.write(f"**{'✅ Approved' if tour['status'] == 'approved' else '❌ Rejected'} by:** {tour.get('approver_name', 'N/A')}")
                    if tour.get('approval_comment'):
                        st.write(f"**💬 Comment:** {tour['approval_comment']}")
            
            with col2:
                # View button (everyone)
                if st.button("👁️ View", key=f"view_{tour['id']}", use_container_width=True):
                    st.session_state.tour_action = "VIEW"
                    st.session_state.selected_tour_id = tour['id']
                    st.rerun()
                
                # Edit button (only if draft/pending and owner or admin)
                can_edit = tour['status'] in ['draft', 'pending'] and (tour['user_id'] == current_user_id or role == 'admin')
                if can_edit:
                    if st.button("✏️ Edit", key=f"edit_{tour['id']}", use_container_width=True):
                        st.session_state.tour_action = "EDIT"
                        st.session_state.selected_tour_id = tour['id']
                        st.rerun()
                else:
                    st.button("✏️ Edit", key=f"edit_{tour['id']}", disabled=True, use_container_width=True, help="Cannot edit")
                
                # Delete button (only if draft/pending and owner or admin)
                can_delete = tour['status'] in ['draft', 'pending'] and (tour['user_id'] == current_user_id or role == 'admin')
                if can_delete:
                    if st.button("🗑️ Delete", key=f"delete_{tour['id']}", use_container_width=True):
                        if st.session_state.get(f"confirm_delete_{tour['id']}"):
                            from modules.dcr.tour_database import delete_tour_programme
                            delete_tour_programme(tour['id'])
                            st.success("Tour deleted!")
                            st.rerun()
                        else:
                            st.session_state[f"confirm_delete_{tour['id']}"] = True
                            st.warning("Click again to confirm")
                else:
                    st.button("🗑️ Delete", key=f"delete_{tour['id']}", disabled=True, use_container_width=True, help="Cannot delete")
                
                # Admin: Approve/Reject buttons (only if pending)
                if role == "admin" and tour['status'] == 'pending':
                    st.write("---")
                    if st.button("✅ Approve", key=f"approve_{tour['id']}", use_container_width=True, type="primary"):
                        st.session_state.tour_action = "APPROVE"
                        st.session_state.selected_tour_id = tour['id']
                        st.rerun()
                    
                    if st.button("❌ Reject", key=f"reject_{tour['id']}", use_container_width=True):
                        st.session_state.tour_action = "REJECT"
                        st.session_state.selected_tour_id = tour['id']
                        st.rerun()

def show_approve_tour():
    """Admin approves tour"""
    st.write("### ✅ Approve Tour Programme")
    
    from modules.dcr.tour_database import approve_tour_programme, get_tour_by_id
    
    tour_id = st.session_state.selected_tour_id
    tour = get_tour_by_id(tour_id)
    
    if not tour:
        st.error("Tour not found")
        return
    
    st.write(f"**Tour Date:** {tour['tour_date']}")
    st.write(f"**Territories:** {', '.join([t['name'] for t in tour.get('territories', [])])}")
    
    comment = st.text_area("Approval Comment (Optional)", placeholder="Looks good!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Confirm Approval", type="primary"):
            approve_tour_programme(tour_id, get_current_user_id(), comment)
            st.success("Tour approved!")
            st.session_state.tour_action = None
            st.session_state.selected_tour_id = None
            st.rerun()
    
    with col2:
        if st.button("❌ Cancel"):
            st.session_state.tour_action = None
            st.session_state.selected_tour_id = None
            st.rerun()


def show_reject_tour():
    """Admin rejects tour"""
    st.write("### ❌ Reject Tour Programme")
    
    from modules.dcr.tour_database import reject_tour_programme, get_tour_by_id
    
    tour_id = st.session_state.selected_tour_id
    tour = get_tour_by_id(tour_id)
    
    if not tour:
        st.error("Tour not found")
        return
    
    st.write(f"**Tour Date:** {tour['tour_date']}")
    st.write(f"**Territories:** {', '.join([t['name'] for t in tour.get('territories', [])])}")
    
    comment = st.text_area("Rejection Reason *", placeholder="Please revise...")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("❌ Confirm Rejection", type="primary"):
            if not comment:
                st.error("Please provide a reason")
            else:
                reject_tour_programme(tour_id, get_current_user_id(), comment)
                st.success("Tour rejected!")
                st.session_state.tour_action = None
                st.session_state.selected_tour_id = None
                st.rerun()
    
    with col2:
        if st.button("Cancel"):
            st.session_state.tour_action = None
            st.session_state.selected_tour_id = None
            st.rerun()

def show_create_tour_form():
    """
    Form to create new tour programme
    """
    st.write("### ➕ Create Tour Programme")
    
    current_user_id = get_current_user_id()
    role = st.session_state.get("role", "user")
    
    # Initialize form counter for unique keys
    if "tour_form_counter" not in st.session_state:
        st.session_state.tour_form_counter = 0
    
    # Initialize selected user in session state
    if "tour_create_selected_user" not in st.session_state:
        st.session_state.tour_create_selected_user = current_user_id
    
    # Initialize selected territories in session state
    if "tour_create_territories" not in st.session_state:
        st.session_state.tour_create_territories = []
    
    # Back button
    if st.button("⬅️ Back to List"):
        st.session_state.tour_action = None
        st.session_state.create_another = False
        st.session_state.tour_form_counter = 0
        st.session_state.pop("tour_create_selected_user", None)
        st.session_state.pop("tour_create_territories", None)
        st.rerun()
    
    st.write("---")
    
    # Admin: Select user (OUTSIDE FORM)
    if role == "admin":
        st.write("### 👤 Admin: Select User")
        
        from modules.dcr.masters_database import get_all_users
        users = get_all_users()
        
        user_options = {u['id']: u['username'] for u in users}
        
        selected_user_id = st.selectbox(
            "Create tour programme for:",
            options=list(user_options.keys()),
            format_func=lambda x: user_options[x],
            index=list(user_options.keys()).index(st.session_state.tour_create_selected_user) if st.session_state.tour_create_selected_user in user_options else 0,
            key="tour_user_selector"
        )
        
        # Update session state
        st.session_state.tour_create_selected_user = selected_user_id
        
        st.info(f"Creating tour for: **{user_options[selected_user_id]}**")
        st.write("---")
    else:
        selected_user_id = current_user_id
        st.session_state.tour_create_selected_user = selected_user_id
    
    # Get user territories
    user_territories = get_user_territories(selected_user_id)
    
    if not user_territories:
        st.error(f"No territories assigned to {'this user' if role == 'admin' else 'you'}!")
        return
    
    # Territory selection using MULTISELECT (no duplicate key issues)
    st.write("### 🗺️ Select Territories *")
    
    territory_options = {t['id']: t['name'] for t in user_territories}
    
    selected_territories = st.multiselect(
        "Choose one or more territories:",
        options=list(territory_options.keys()),
        default=st.session_state.tour_create_territories,
        format_func=lambda x: territory_options[x],
        key=f"territory_multi_{st.session_state.tour_form_counter}"
    )
    
    # Update session state
    st.session_state.tour_create_territories = selected_territories
    
    st.info(f"✓ Selected: {len(selected_territories)} territories")
    
    if not selected_territories:
        st.warning("⚠️ Please select at least one territory to continue")
        return

    
    st.write("---")
    
    # Form counter for unique keys
    form_suffix = st.session_state.tour_form_counter
    
    # TEMPORARY TEST: Use DCR functions directly
    st.write("🧪 TESTING DCR FUNCTIONS DIRECTLY:")
    try:
        from modules.dcr.dcr_database import get_doctors_by_territories as dcr_get_docs
        from modules.dcr.dcr_database import get_chemists_by_territories as dcr_get_chems
        
        test_docs = dcr_get_docs(selected_territories)
        test_chems = dcr_get_chems(selected_territories)
        
        st.success(f"✅ DCR functions work! Docs: {len(test_docs)}, Chems: {len(test_chems)}")
        
        if test_docs:
            st.write("Sample doctor:", test_docs[0])
        if test_chems:
            st.write("Sample chemist:", test_chems[0])
            
    except Exception as e:
        st.error(f"❌ DCR functions also fail: {str(e)}")
    # Get doctors and chemists based on selected territories
    st.write("🔍 DEBUG: About to load doctors...")
    st.write(f"Selected territories: {selected_territories}")
    st.write(f"Territory IDs type: {type(selected_territories)}")
    
    try:
        doctors = get_doctors_by_territories(selected_territories)
        st.write(f"✅ Doctors loaded: {len(doctors)}")
    except Exception as e:
        st.error(f"❌ Error loading doctors: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        doctors = []
    
    try:
        chemists = get_chemists_by_territories(selected_territories)
        st.write(f"✅ Chemists loaded: {len(chemists)}")
    except Exception as e:
        st.error(f"❌ Error loading chemists: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        chemists = []
    # DEBUG OUTPUT
    st.write("🔍 **DEBUG INFO:**")
    st.write(f"Selected territory IDs: {selected_territories}")
    st.write(f"Doctors found: {len(doctors) if doctors else 0}")
    st.write(f"Chemists found: {len(chemists) if chemists else 0}")
    if doctors:
        st.write("Doctor names:", [d['name'] for d in doctors])
    if chemists:
        st.write("Chemist names:", [c['name'] for c in chemists])
    st.write("---")
    
    # THE FORM STARTS HERE
    with st.form(f"tour_create_{form_suffix}", clear_on_submit=False):
        # Tour date
        tour_date = st.date_input(
            "Tour Date *",
            value=date.today() + timedelta(days=1),
            min_value=date.today()
        )
        
        st.write("---")
        st.write("#### 👥 Worked With *")
        
        worked_with_type = st.radio(
            "Select one:",
            options=["alone", "with_manager", "with_senior", "with_admin"],
            format_func=lambda x: {
                "alone": "Alone",
                "with_manager": "With Manager",
                "with_senior": "With Manager + Senior Manager",
                "with_admin": "With Admin"
            }[x],
            horizontal=True
        )
        
        st.write("---")
        st.write("#### 👨‍⚕️ Doctors to Visit (Optional)")
        
        selected_doctor_ids = []
        if doctors:
            for idx, doctor in enumerate(doctors):
                if st.checkbox(
                    f"{doctor['name']} ({doctor.get('specialization', 'N/A')})",
                    value=False,
                    key=f"d_{idx}_{form_suffix}"
                ):
                    selected_doctor_ids.append(doctor['id'])
        else:
            st.info("No doctors available in selected territories")
        
        st.info(f"✓ Selected: {len(selected_doctor_ids)} doctors")
        
        st.write("---")
        st.write("#### 🏪 Chemists to Visit (Optional)")
        
        selected_chemist_ids = []
        if chemists:
            for idx, chemist in enumerate(chemists):
                if st.checkbox(
                    f"{chemist['name']} ({chemist.get('shop_name', 'N/A')})",
                    value=False,
                    key=f"c_{idx}_{form_suffix}"
                ):
                    selected_chemist_ids.append(chemist['id'])
        else:
            st.info("No chemists available in selected territories")
        
        st.info(f"✓ Selected: {len(selected_chemist_ids)} chemists")
        
        st.write("---")
        
        notes = st.text_area("📝 Notes (Optional)", placeholder="Instructions...")
        
        st.write("---")
        
        # Submit buttons
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            submit_draft = st.form_submit_button("💾 Save Draft", use_container_width=True)
        with col2:
            submit_pending = st.form_submit_button("✅ Save & Submit", type="primary", use_container_width=True)
        with col3:
            submit_next = st.form_submit_button("➕ Save & Create Next", use_container_width=True)
        with col4:
            cancel = st.form_submit_button("❌ Cancel", use_container_width=True)
    
    # Handle submission (OUTSIDE FORM)
    if submit_draft or submit_pending or submit_next:
        if not selected_territories:
            st.error("❌ Please select at least one territory")
        else:
            try:
                status = "draft" if submit_draft else "pending"
                
                tour_id = create_tour_programme(
                    user_id=st.session_state.tour_create_selected_user,
                    tour_date=tour_date,
                    territory_ids=selected_territories,
                    worked_with_type=worked_with_type,
                    doctor_ids=selected_doctor_ids,
                    chemist_ids=selected_chemist_ids,
                    notes=notes,
                    status=status
                )
                
                if submit_next:
                    st.success(f"✅ Tour for {tour_date} created! Create next tour below.")
                    st.session_state.tour_form_counter += 1
                    st.session_state.tour_create_territories = []  # Reset territories
                    st.rerun()
                else:
                    st.success(f"✅ Tour programme {'saved as draft' if submit_draft else 'submitted'}!")
                    st.session_state.tour_action = None
                    st.session_state.tour_form_counter = 0
                    st.session_state.pop("tour_create_selected_user", None)
                    st.session_state.pop("tour_create_territories", None)
                    st.rerun()
            
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    if cancel:
        st.session_state.tour_action = None
        st.session_state.tour_form_counter = 0
        st.session_state.pop("tour_create_selected_user", None)
        st.session_state.pop("tour_create_territories", None)
        st.rerun()
def show_edit_tour_form():
    """
    Form to edit existing tour (only if draft/pending)
    """
    st.write("### ✏️ Edit Tour Programme")
    
    tour_id = st.session_state.selected_tour_id
    tour = get_tour_by_id(tour_id)
    
    if not tour:
        st.error("Tour not found")
        return
    
    # Check if editable
    if tour['status'] not in ['draft', 'pending']:
        st.error("❌ Cannot edit approved/rejected tours")
        if st.button("⬅️ Back"):
            st.session_state.tour_action = None
            st.rerun()
        return
    
    current_user_id = get_current_user_id()
    
    # Back button
    if st.button("⬅️ Back to List"):
        st.session_state.tour_action = None
        st.session_state.selected_tour_id = None
        st.rerun()
    
    st.write("---")
    
    # Pre-load data
    existing_territory_ids = tour['territory_ids']
    existing_doctor_ids = tour['doctor_ids']
    existing_chemist_ids = tour['chemist_ids']
    
    # Form (similar to create, but pre-filled)
    with st.form("edit_tour_form"):
        # Tour date
        tour_date = st.date_input(
            "Tour Date *",
            value=datetime.strptime(tour['tour_date'], '%Y-%m-%d').date(),
            min_value=date.today()
        )
        
        st.write("---")
        
        # Territories
        st.write("#### 🗺️ Territories *")
        user_territories = get_user_territories(current_user_id)
        
        selected_territories = []
        for territory in user_territories:
            default = territory['id'] in existing_territory_ids
            if st.checkbox(
                territory['name'],
                value=default,
                key=f"terr_edit_{territory['id']}"
            ):
                selected_territories.append(territory['id'])
        
        st.info(f"✓ Selected: {len(selected_territories)} territories")
        
        st.write("---")
        
        # Worked with
        st.write("#### 👥 Worked With *")
        worked_with_type = st.radio(
            "Select one:",
            options=["alone", "with_manager", "with_senior", "with_admin"],
            format_func=lambda x: {
                "alone": "Alone",
                "with_manager": "With Manager",
                "with_senior": "With Manager + Senior Manager",
                "with_admin": "With Admin"
            }[x],
            index=["alone", "with_manager", "with_senior", "with_admin"].index(tour['worked_with_type']),
            horizontal=True
        )
        
        st.write("---")
        
        # Doctors
        st.write("#### 👨‍⚕️ Doctors to Visit (Optional)")
        
        selected_doctor_ids = []
        if selected_territories:
            doctors = get_doctors_by_territories(selected_territories)
            if doctors:
                for doctor in doctors:
                    default = doctor['id'] in existing_doctor_ids
                    if st.checkbox(
                        f"{doctor['name']} ({doctor.get('specialization', 'N/A')})",
                        value=default,
                        key=f"doc_edit_{doctor['id']}"
                    ):
                        selected_doctor_ids.append(doctor['id'])
        
        st.info(f"✓ Selected: {len(selected_doctor_ids)} doctors")
        
        st.write("---")
        
        # Chemists
        st.write("#### 🏪 Chemists to Visit (Optional)")
        
        selected_chemist_ids = []
        if selected_territories:
            chemists = get_chemists_by_territories(selected_territories)
            if chemists:
                for chemist in chemists:
                    default = chemist['id'] in existing_chemist_ids
                    if st.checkbox(
                        f"{chemist['name']} ({chemist.get('shop_name', 'N/A')})",
                        value=default,
                        key=f"chem_edit_{chemist['id']}"
                    ):
                        selected_chemist_ids.append(chemist['id'])
        
        st.info(f"✓ Selected: {len(selected_chemist_ids)} chemists")
        
        st.write("---")
        
        # Notes
        notes = st.text_area("📝 Notes (Optional)", value=tour.get('notes', ''))
        
        st.write("---")
        
        # Submit buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            submit_draft = st.form_submit_button("💾 Save as Draft", use_container_width=True)
        with col2:
            submit_pending = st.form_submit_button("✅ Update & Submit", type="primary", use_container_width=True)
        with col3:
            cancel = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if submit_draft or submit_pending:
            if not selected_territories:
                st.error("❌ Please select at least one territory")
            else:
                try:
                    status = "draft" if submit_draft else "pending"
                    
                    update_tour_programme(
                        tour_id=tour_id,
                        tour_date=tour_date,
                        territory_ids=selected_territories,
                        worked_with_type=worked_with_type,
                        doctor_ids=selected_doctor_ids,
                        chemist_ids=selected_chemist_ids,
                        notes=notes,
                        status=status
                    )
                    
                    st.success("✅ Tour programme updated!")
                    st.session_state.tour_action = None
                    st.session_state.selected_tour_id = None
                    st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        if cancel:
            st.session_state.tour_action = None
            st.session_state.selected_tour_id = None
            st.rerun()


def show_view_tour():
    """
    View tour programme details (read-only)
    """
    tour_id = st.session_state.selected_tour_id
    tour = get_tour_by_id(tour_id)
    
    if not tour:
        st.error("Tour not found")
        return
    
    st.write(f"### 👁 Tour Programme - {tour['tour_date']}")
    
    # Status badge
    status_emoji = {
        "draft": "📝",
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌"
    }.get(tour['status'], "📝")
    
    st.write(f"**Status:** {status_emoji} {tour['status'].upper()}")
    
    # Action buttons
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("⬅️ Back", use_container_width=True):
            st.session_state.tour_action = None
            st.session_state.selected_tour_id = None
            st.rerun()
    
    with col2:
        if tour['status'] in ['draft', 'pending']:
            if st.button("✏️ Edit", use_container_width=True):
                st.session_state.tour_action = "EDIT"
                st.rerun()
    
    st.write("---")
    
    # Tour details
    st.write(f"**📅 Tour Date:** {tour['tour_date']}")
    st.write(f"**🗺️ Territories:** {', '.join([t['name'] for t in tour['territories']])}")
    st.write(f"**👥 Worked With:** {tour['worked_with_type'].replace('_', ' ').title()}")
    
    st.write("---")
    
    # Doctors
    st.write("**👨‍⚕️ Doctors to Visit:**")
    if tour['doctors']:
        for doctor in tour['doctors']:
            st.write(f"• {doctor['name']} ({doctor.get('specialization', 'N/A')})")
    else:
        st.info("No doctors planned")
    
    st.write("---")
    
    # Chemists
    st.write("**🏪 Chemists to Visit:**")
    if tour['chemists']:
        for chemist in tour['chemists']:
            st.write(f"• {chemist['name']} ({chemist.get('shop_name', 'N/A')})")
    else:
        st.info("No chemists planned")
    
    st.write("---")
    
    # Notes
    if tour.get('notes'):
        st.write("**📝 Notes:**")
        st.write(tour['notes'])
        st.write("---")
    
    # Approval details
    if tour['status'] in ['approved', 'rejected']:
        st.write(f"**{'✅ APPROVED' if tour['status'] == 'approved' else '❌ REJECTED'} BY:**")
        st.write(f"• {tour.get('approver_name', 'Unknown')}")
        st.write(f"• On: {tour['approved_at'][:10] if tour.get('approved_at') else 'N/A'}")
        if tour.get('approval_comment'):
            st.write(f"• Comment: {tour['approval_comment']}")
