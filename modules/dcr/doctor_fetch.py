"""
Doctor Fetch Module
Allows users to update doctor details and view 360 degree profiles
"""

import streamlit as st
from modules.dcr.dcr_database import safe_exec, get_user_territories
from modules.dcr.dcr_helpers import get_current_user_id
from anchors.supabase_client import admin_supabase


def run_doctor_fetch():
    """
    Main entry point for Doctor Fetch module
    """
    st.title("🔍 Doctor Fetch")
    
    # Show options
    if "doctor_fetch_mode" not in st.session_state:
        st.session_state.doctor_fetch_mode = None
    
    if not st.session_state.doctor_fetch_mode:
        show_doctor_fetch_home()
    elif st.session_state.doctor_fetch_mode == "UPDATE":
        show_update_doctor_flow()
    elif st.session_state.doctor_fetch_mode == "FETCH":
        show_fetch_doctor_flow()


def show_doctor_fetch_home():
    """
    Home screen with Update/Fetch options
    """
    st.write("### What would you like to do?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✏️ Update Doctor Details", use_container_width=True, type="primary"):
            st.session_state.doctor_fetch_mode = "UPDATE"
            st.rerun()
    
    with col2:
        if st.button("📊 Fetch Doctor Details", use_container_width=True):
            st.session_state.doctor_fetch_mode = "FETCH"
            st.rerun()
    
    if st.button("🏠 Home"):
        st.session_state.active_module = None
        st.rerun()


def show_update_doctor_flow():
    """
    Update doctor: Territory -> Doctor -> Update Form
    """
    st.write("### ✏️ Update Doctor Details")
    
    # Step 1: Territory selection
    if "doctor_fetch_territory" not in st.session_state:
        user_id = get_current_user_id()
        territories = get_user_territories(user_id)
        
        if not territories:
            st.warning("No territories assigned to you")
            if st.button("⬅️ Back"):
                st.session_state.doctor_fetch_mode = None
                st.rerun()
            return
        
        selected_territory = st.selectbox(
            "Select Territory",
            options=[t["id"] for t in territories],
            format_func=lambda x: next(t["name"] for t in territories if t["id"] == x)
        )
        
        if st.button("Next"):
            st.session_state.doctor_fetch_territory = selected_territory
            st.rerun()
        
        if st.button("⬅️ Back"):
            st.session_state.doctor_fetch_mode = None
            st.rerun()
        return
    
    # Step 2: Doctor selection
    if "doctor_fetch_doctor_id" not in st.session_state:
        territory_id = st.session_state.doctor_fetch_territory
        
        doctors = safe_exec(
            admin_supabase.table("doctor_territories")
            .select("doctors(id, name, specialization)")
            .eq("territory_id", territory_id),
            "Error loading doctors"
        )
        
        doctor_list = [d["doctors"] for d in doctors if d.get("doctors")]
        
        if not doctor_list:
            st.warning("No doctors found in this territory")
            if st.button("⬅️ Back"):
                del st.session_state.doctor_fetch_territory
                st.rerun()
            return
        
        selected_doctor = st.selectbox(
            "Select Doctor",
            options=[d["id"] for d in doctor_list],
            format_func=lambda x: next(d["name"] for d in doctor_list if d["id"] == x)
        )
        
        if st.button("Next"):
            st.session_state.doctor_fetch_doctor_id = selected_doctor
            st.rerun()
        
        if st.button("⬅️ Back"):
            del st.session_state.doctor_fetch_territory
            st.rerun()
        return
    
    # Step 3: Update form
    show_doctor_update_form()


def show_doctor_update_form():
    """
    Form to update doctor details
    """
    doctor_id = st.session_state.doctor_fetch_doctor_id
    
    # Load doctor data
    doctor = safe_exec(
        admin_supabase.table("doctors")
        .select("*")
        .eq("id", doctor_id)
        .limit(1),
        "Error loading doctor"
    )
    
    if not doctor:
        st.error("Doctor not found")
        return
    
    doc = doctor[0]
    
    st.write(f"### {doc['name']}")
    st.write(f"**Specialty:** {doc.get('specialization', 'Not specified')}")
    
    st.write("---")
    
    # Date of Birth (locked if already filled)
    st.write("#### 📅 Special Dates")
    
    if doc.get("date_of_birth"):
        st.text_input("Date of Birth", value=str(doc["date_of_birth"]), disabled=True, 
                     help="Already saved - cannot edit")
        new_dob = None
    else:
        new_dob = st.date_input("Date of Birth (Optional)", value=None)
    
    # Date of Anniversary (locked if already filled)
    if doc.get("date_of_anniversary"):
        st.text_input("Date of Anniversary", value=str(doc["date_of_anniversary"]), disabled=True,
                     help="Already saved - cannot edit")
        new_doa = None
    else:
        new_doa = st.date_input("Date of Anniversary (Optional)", value=None)
    
    st.write("---")
    
    # Locations
    st.write("#### 📍 Locations (Max 3)")
    st.info("💡 Click 'Fetch Location' to auto-fill GPS coordinates from your phone")
    
    existing_locations = safe_exec(
        admin_supabase.table("doctor_locations")
        .select("*")
        .eq("doctor_id", doctor_id)
        .eq("is_active", True)
        .order("added_at"),
        "Error loading locations"
    )
    
    # Show existing locations
    for idx, loc in enumerate(existing_locations):
        with st.expander(f"Location {idx+1}: {loc['location_name']}"):
            st.write(f"📍 Lat: {loc['latitude']}, Long: {loc['longitude']}")
            st.write(f"Added: {loc['added_at']}")
    
    # New location form (if under 3)
    if len(existing_locations) < 3:
        st.write(f"**Add New Location ({len(existing_locations)}/3 saved)**")
        
        new_loc_name = st.text_input("Location Name", placeholder="e.g., City Hospital Main Gate")
        
        col1, col2 = st.columns(2)
        with col1:
            new_lat = st.number_input("Latitude", format="%.8f", value=0.0)
        with col2:
            new_long = st.number_input("Longitude", format="%.8f", value=0.0)
        
        st.warning("📱 To fetch your current location, please enable GPS/Location services on your phone")
        
        if st.button("📍 Fetch My Current Location"):
            st.info("🚧 GPS fetch feature coming soon. For now, please enter coordinates manually.")
    
    st.write("---")
    
    # Remarks
    st.write("#### 📝 Remarks")
    
    existing_remarks = safe_exec(
        admin_supabase.table("doctor_remarks")
        .select("*")
        .eq("doctor_id", doctor_id)
        .eq("is_deleted", False)
        .order("added_at", desc=True),
        "Error loading remarks"
    )
    
    if existing_remarks:
        st.write("**Previous Remarks:**")
        for remark in existing_remarks:
            st.write(f"• {remark['added_at'][:10]}: {remark['remark_text']}")
    
    new_remark = st.text_area("Add New Remark (Optional)", placeholder="Enter your notes about this doctor")
    
    st.write("---")
    
    # Submit button
    if st.button("💾 Save Changes", type="primary"):
        current_user_id = get_current_user_id()
        
        # Update DOB if new
        if new_dob:
            safe_exec(
                admin_supabase.table("doctors")
                .update({"date_of_birth": str(new_dob), "updated_by": current_user_id})
                .eq("id", doctor_id),
                "Error updating DOB"
            )
        
        # Update DOA if new
        if new_doa:
            safe_exec(
                admin_supabase.table("doctors")
                .update({"date_of_anniversary": str(new_doa), "updated_by": current_user_id})
                .eq("id", doctor_id),
                "Error updating DOA"
            )
        
        # Add new location if filled
        if new_loc_name and (new_lat != 0.0 or new_long != 0.0):
            safe_exec(
                admin_supabase.table("doctor_locations").insert({
                    "doctor_id": doctor_id,
                    "location_name": new_loc_name,
                    "latitude": new_lat,
                    "longitude": new_long,
                    "added_by": current_user_id
                }),
                "Error adding location"
            )
        
        # Add new remark if filled
        if new_remark and new_remark.strip():
            safe_exec(
                admin_supabase.table("doctor_remarks").insert({
                    "doctor_id": doctor_id,
                    "remark_text": new_remark.strip(),
                    "added_by": current_user_id
                }),
                "Error adding remark"
            )
        
        st.success("✅ Doctor details updated successfully!")
        
        # Clear state
        del st.session_state.doctor_fetch_territory
        del st.session_state.doctor_fetch_doctor_id
        st.session_state.doctor_fetch_mode = None
        st.rerun()
    
    if st.button("❌ Cancel"):
        del st.session_state.doctor_fetch_territory
        del st.session_state.doctor_fetch_doctor_id
        st.session_state.doctor_fetch_mode = None
        st.rerun()


def show_fetch_doctor_flow():
    """
    Fetch doctor: Territory -> Doctor -> 360 degree Profile
    """
    st.write("### 📊 Fetch Doctor Details")
    st.info("🚧 360 degree Doctor Profile view coming soon")
    
    if st.button("⬅️ Back"):
        st.session_state.doctor_fetch_mode = None
        st.rerun()
