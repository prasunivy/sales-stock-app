"""
Chemists Master - CRUD Operations
Manage chemists within DCR module
"""

import streamlit as st
from modules.dcr.masters_database import (
    get_chemists_list,
    get_chemist_by_id,
    create_chemist,
    update_chemist,
    delete_chemist_soft,
    get_user_territories,
    get_stockist_by_territory,
    get_all_users
)
from modules.dcr.dcr_helpers import get_current_user_id


def run_chemists_master():
    """
    Main entry point for Chemists Master
    """
    st.title("🏪 Chemists Master")
    
    # Initialize state
    if "chemists_master_action" not in st.session_state:
        st.session_state.chemists_master_action = None
    if "selected_chemist_id" not in st.session_state:
        st.session_state.selected_chemist_id = None
    
    # Route
    action = st.session_state.chemists_master_action
    
    if action == "ADD":
        show_add_chemist_form()
    elif action == "EDIT":
        show_edit_chemist_form()
    else:
        show_chemists_list()


def show_chemists_list():
    """
    Show list of chemists with search and filters
    """
    current_user_id = get_current_user_id()
    role = st.session_state.get("role", "user")
    
    # Back button
    if st.button("⬅️ Back to DCR Home"):
        st.session_state.chemists_master_action = None
        st.session_state.selected_chemist_id = None
        st.session_state.dcr_masters_mode = None  # ← KEY FIX
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
            "View chemists for user:",
            options=list(user_options.keys()),
            format_func=lambda x: user_options[x]
        )
        st.write("---")
    
    # Search and filters
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        search_query = st.text_input("🔍 Search chemists", placeholder="Chemist or shop name...")
    
    with col2:
        user_territories = get_user_territories(selected_user_id)
        territory_filter = st.selectbox(
            "Filter by Territory",
            options=[None] + [t['id'] for t in user_territories],
            format_func=lambda x: "All Territories" if x is None else next((t['name'] for t in user_territories if t['id'] == x), x)
        )
    
    with col3:
        active_only = st.checkbox("Active only", value=True)
    
    # Add button
    if st.button("➕ Add New Chemist", type="primary"):
        st.session_state.chemists_master_action = "ADD"
        st.session_state.chemists_master_selected_user = selected_user_id
        st.rerun()
    
    st.write("---")
    
    # Get chemists
    chemists = get_chemists_list(
        user_id=selected_user_id,
        search=search_query,
        territory_id=territory_filter,
        active_only=active_only
    )
    
    st.write(f"### 📋 Chemists ({len(chemists)} found)")
    
    if not chemists:
        st.info("No chemists found. Click 'Add New Chemist' to create one.")
        return
    
    # Display chemists
    for chemist in chemists:
        with st.expander(f"{chemist['name']} | {chemist.get('shop_name', 'N/A')}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**🏪 Shop:** {chemist.get('shop_name', 'N/A')}")
                st.write(f"**📞 Phone:** {chemist.get('phone', 'N/A')}")
                st.write(f"**📍 Address:** {chemist.get('address', 'N/A')}")
                st.write(f"**🗺️ Territory:** {chemist.get('territory_name', 'N/A')}")
                st.write(f"**🏢 Stockist:** {chemist.get('stockist_name', 'N/A')}")
            
            with col2:
                if st.button("✏️ Edit", key=f"edit_{chemist['id']}"):
                    st.session_state.chemists_master_action = "EDIT"
                    st.session_state.selected_chemist_id = chemist['id']
                    st.session_state.chemists_master_selected_user = selected_user_id
                    st.rerun()
                
                if st.button("🗑️ Delete", key=f"delete_{chemist['id']}"):
                    if st.session_state.get(f"confirm_delete_{chemist['id']}"):
                        delete_chemist_soft(chemist['id'], current_user_id)
                        st.success("Chemist deleted!")
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_{chemist['id']}"] = True
                        st.warning("Click again to confirm")


def show_add_chemist_form():
    """
    Form to add new chemist
    """
    st.write("### ➕ Add New Chemist")
    
    current_user_id = get_current_user_id()
    role = st.session_state.get("role", "user")
    selected_user_id = st.session_state.get("chemists_master_selected_user", current_user_id)
    
    # Back button
    if st.button("⬅️ Back to List"):
        st.session_state.chemists_master_action = None
        st.session_state.selected_chemist_id = None
        st.rerun()
    
    st.write("---")
    
    # Admin sees user selection
    if role == "admin":
        users = get_all_users()
        user_options = {u['id']: u['username'] for u in users}
        st.info(f"Creating chemist for: **{user_options.get(selected_user_id, 'Unknown')}**")
    
    # Get user territories
    user_territories = get_user_territories(selected_user_id)
    
    if not user_territories:
        st.error("No territories assigned to this user!")
        return
    
    # Form
    with st.form("add_chemist_form"):
        # Basic info
        chemist_name = st.text_input("Chemist Name *", placeholder="Ram Medical Store")
        shop_name = st.text_input("Shop Name", placeholder="Ram Medicals")
        phone = st.text_input("Phone", placeholder="+91 98XXXXXXXX")
        address = st.text_area("Address", placeholder="123 Main St, City")
        
        st.write("---")
        
        # Territory (single selection)
        st.write("#### Territory * (Select One)")
        
        if role == "user":
            if len(user_territories) == 1:
                selected_territory = user_territories[0]['id']
                st.info(f"Your territory: {user_territories[0]['name']}")
            else:
                selected_territory = st.radio(
                    "Select territory:",
                    options=[t['id'] for t in user_territories],
                    format_func=lambda x: next((t['name'] for t in user_territories if t['id'] == x), x)
                )
        else:
            selected_territory = st.radio(
                f"Select territory for {user_options.get(selected_user_id)}:",
                options=[t['id'] for t in user_territories],
                format_func=lambda x: next((t['name'] for t in user_territories if t['id'] == x), x)
            )
        
        st.write("---")
        
        # Stockist (auto-populated based on territory)
        st.write("#### Stockist * (Based on Territory)")
        
        stockist = get_stockist_by_territory(selected_territory) if selected_territory else None
        
        if stockist:
            st.info(f"Stockist: **{stockist['name']}**")
            selected_stockist = stockist['id']
        else:
            st.error("No stockist found for selected territory!")
            selected_stockist = None
        
        # Submit
        submitted = st.form_submit_button("💾 Save Chemist", type="primary")
        
        if submitted:
            if not chemist_name:
                st.error("Chemist name is required")
            elif not selected_territory:
                st.error("Please select a territory")
            elif not selected_stockist:
                st.error("No stockist available for selected territory")
            else:
                try:
                    create_chemist(
                        name=chemist_name,
                        shop_name=shop_name,
                        phone=phone,
                        address=address,
                        territory_id=selected_territory,
                        stockist_id=selected_stockist,
                        created_by=current_user_id
                    )
                    st.success("✅ Chemist created successfully!")
                    st.session_state.chemists_master_action = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating chemist: {str(e)}")


def show_edit_chemist_form():
    """
    Form to edit existing chemist
    """
    st.write("### ✏️ Edit Chemist")
    
    chemist_id = st.session_state.selected_chemist_id
    current_user_id = get_current_user_id()
    
    # Back button
    if st.button("⬅️ Back to List"):
        st.session_state.chemists_master_action = None
        st.session_state.selected_chemist_id = None
        st.rerun()
    
    # Load chemist
    chemist = get_chemist_by_id(chemist_id)
    
    if not chemist:
        st.error("Chemist not found")
        return
    
    st.write("---")
    
    # Form (pre-filled)
    with st.form("edit_chemist_form"):
        chemist_name = st.text_input("Chemist Name *", value=chemist['name'])
        shop_name = st.text_input("Shop Name", value=chemist.get('shop_name', ''))
        phone = st.text_input("Phone", value=chemist.get('phone', ''))
        address = st.text_area("Address", value=chemist.get('address', ''))
        
        st.write("---")
        st.write("#### Territory")
        st.info(f"Territory: **{chemist.get('territory_name', 'N/A')}** (cannot be changed)")
        
        st.write("---")
        st.write("#### Stockist")
        st.info(f"Stockist: **{chemist.get('stockist_name', 'N/A')}** (auto-assigned by territory)")
        
        # Submit
        submitted = st.form_submit_button("💾 Update Chemist", type="primary")
        
        if submitted:
            if not chemist_name:
                st.error("Chemist name is required")
            else:
                try:
                    update_chemist(
                        chemist_id=chemist_id,
                        name=chemist_name,
                        shop_name=shop_name,
                        phone=phone,
                        address=address,
                        updated_by=current_user_id
                    )
                    st.success("✅ Chemist updated successfully!")
                    st.session_state.chemists_master_action = None
                    st.session_state.selected_chemist_id = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error updating chemist: {str(e)}")
