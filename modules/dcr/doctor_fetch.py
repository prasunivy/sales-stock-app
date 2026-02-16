"""
Doctor Fetch Module
Allows users to update doctor details and view 360 degree profiles
"""

import streamlit as st
from datetime import datetime, date, timedelta
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
    
    if st.button("🏠 Back to DCR Home"):
        st.session_state.engine_stage = "dcr"
        st.session_state.doctor_fetch_mode = None
        # Clear any doctor fetch session keys
        for key in ["doctor_fetch_territory", "doctor_fetch_doctor_id"]:
            if key in st.session_state:
                del st.session_state[key]
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
    st.write("### 📊 360° Doctor Profile")
    
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
            format_func=lambda x: next(t["name"] for t in territories if t["id"] == x),
            key="fetch_territory_select"
        )
        
        if st.button("Next", key="fetch_territory_next"):
            st.session_state.doctor_fetch_territory = selected_territory
            st.rerun()
        
        if st.button("⬅️ Back", key="fetch_territory_back"):
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
            if st.button("⬅️ Back", key="fetch_doctor_back"):
                del st.session_state.doctor_fetch_territory
                st.rerun()
            return
        
        selected_doctor = st.selectbox(
            "Select Doctor",
            options=[d["id"] for d in doctor_list],
            format_func=lambda x: next(f"{d['name']} ({d.get('specialization', 'N/A')})" for d in doctor_list if d["id"] == x),
            key="fetch_doctor_select"
        )
        
        if st.button("View Profile", type="primary", key="fetch_doctor_view"):
            st.session_state.doctor_fetch_doctor_id = selected_doctor
            st.rerun()
        
        if st.button("⬅️ Back", key="fetch_doctor_back2"):
            del st.session_state.doctor_fetch_territory
            st.rerun()
        return
    
    # Step 3: Show 360° Profile
    show_doctor_360_profile()


def show_doctor_360_profile():
    """
    Complete 360° doctor profile with all information
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
    
    # ========================================
    # LOAD ALL DATA UPFRONT (before expanders)
    # ========================================
    
    # Load territories
    territories = safe_exec(
        admin_supabase.table("doctor_territories")
        .select("territories(id, name)")
        .eq("doctor_id", doctor_id),
        "Error loading territories"
    )
    territory_ids = [t['territories']['id'] for t in territories if t.get('territories')]
    
    # Load locations
    locations = safe_exec(
        admin_supabase.table("doctor_locations")
        .select("*")
        .eq("doctor_id", doctor_id)
        .eq("is_active", True)
        .order("added_at"),
        "Error loading locations"
    )
    
    # Load stockists
    stockists = safe_exec(
        admin_supabase.table("doctor_stockists")
        .select("stockists(name)")
        .eq("doctor_id", doctor_id),
        "Error loading stockists"
    )
    
    # Load chemists (from territories)
    chemists = []
    if territory_ids:
        chemists = safe_exec(
            admin_supabase.table("chemists")
            .select("name, shop_name")
            .in_("territory_id", territory_ids)
            .eq("is_active", True)
            .order("name"),
            "Error loading chemists"
        )
    
    # Load visit history (last 30 days)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).date()
    
    # First, get recent DCR IDs
    recent_dcrs = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("id, report_date, user_id, users(username)")
        .gte("report_date", str(thirty_days_ago))
        .order("report_date", desc=True),
        "Error loading recent DCRs"
    )
    
    recent_dcr_ids = [dcr['id'] for dcr in recent_dcrs]
    
    # Then get visits for this doctor in those DCRs
    visits = []
    if recent_dcr_ids:
        visits_raw = safe_exec(
            admin_supabase.table("dcr_doctor_visits")
            .select("*")
            .eq("doctor_id", doctor_id)
            .in_("dcr_report_id", recent_dcr_ids),
            "Error loading visit history"
        )
        
        # Enrich visits with DCR data
        for visit in visits_raw:
            dcr = next((d for d in recent_dcrs if d['id'] == visit['dcr_report_id']), None)
            if dcr:
                visit['dcr_reports'] = dcr
                visits.append(visit)
        
        # Sort by date (newest first)
        visits.sort(key=lambda x: x.get('dcr_reports', {}).get('report_date', ''), reverse=True)
    
    # Load remarks
    remarks = safe_exec(
        admin_supabase.table("doctor_remarks")
        .select("*, users(username)")
        .eq("doctor_id", doctor_id)
        .eq("is_deleted", False)
        .order("added_at", desc=True)
        .limit(10),
        "Error loading remarks"
    )
    
    # ========================================
    # DISPLAY PROFILE
    # ========================================
    
    # Header
    st.write(f"# 👨‍⚕️ Dr. {doc['name']}")
    st.write(f"### {doc.get('specialization', 'Specialist')}")
    
    # Action buttons at top
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    with col_btn1:
        if st.button("✏️ Update Details", use_container_width=True):
            st.session_state.doctor_fetch_mode = "UPDATE"
            st.rerun()
    with col_btn2:
        if st.button("📄 Export PDF", use_container_width=True):
            st.info("🚧 PDF export coming soon")
    with col_btn3:
        if st.button("⬅️ Back", use_container_width=True):
            del st.session_state.doctor_fetch_territory
            del st.session_state.doctor_fetch_doctor_id
            st.rerun()
    
    st.write("---")
    
    # ========================================
    # SECTION 1: BASIC INFORMATION
    # ========================================
    with st.expander("📋 BASIC INFORMATION", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**📞 Phone:** {doc.get('phone', 'N/A')}")
            st.write(f"**🏥 Clinic:** {doc.get('clinic_address', 'N/A')}")
        
        with col2:
            # Birthday with countdown
            if doc.get('date_of_birth'):
                dob = datetime.strptime(str(doc['date_of_birth']), '%Y-%m-%d').date()
                days_to_birthday = calculate_days_to_next_occurrence(dob)
                birthday_emoji = "🎂" if days_to_birthday <= 30 else "📅"
                st.write(f"**{birthday_emoji} Birthday:** {dob.strftime('%b %d')} (in {days_to_birthday} days)")
            else:
                st.write("**📅 Birthday:** Not set")
            
            # Anniversary with countdown
            if doc.get('date_of_anniversary'):
                doa = datetime.strptime(str(doc['date_of_anniversary']), '%Y-%m-%d').date()
                days_to_anniversary = calculate_days_to_next_occurrence(doa)
                anniversary_emoji = "💐" if days_to_anniversary <= 30 else "📅"
                st.write(f"**{anniversary_emoji} Anniversary:** {doa.strftime('%b %d')} (in {days_to_anniversary} days)")
            else:
                st.write("**📅 Anniversary:** Not set")
    
    # ========================================
    # SECTION 2: LOCATIONS
    # ========================================
    with st.expander("📍 LOCATIONS", expanded=False):
        if locations:
            for idx, loc in enumerate(locations):
                st.write(f"**{idx+1}. {loc['location_name']}**")
                st.write(f"   📍 Coordinates: {loc['latitude']}, {loc['longitude']}")
                st.write(f"   🕒 Added: {loc['added_at'][:10]}")
                st.write("")
        else:
            st.info("No locations saved yet")
    
    # ========================================
    # SECTION 3: TERRITORIES & COVERAGE
    # ========================================
    with st.expander("🗺️ TERRITORIES & COVERAGE", expanded=False):
        if territories:
            territory_names = [t['territories']['name'] for t in territories if t.get('territories')]
            for name in territory_names:
                st.write(f"• {name}")
        else:
            st.info("No territories assigned")
    
    # ========================================
    # SECTION 4: LINKED STOCKISTS
    # ========================================
    with st.expander("🏢 LINKED STOCKISTS", expanded=False):
        if stockists:
            stockist_names = [s['stockists']['name'] for s in stockists if s.get('stockists')]
            for name in stockist_names:
                st.write(f"• {name}")
        else:
            st.info("No stockists linked")
    
    # ========================================
    # SECTION 5: LINKED CHEMISTS
    # ========================================
    with st.expander("💊 LINKED CHEMISTS", expanded=False):
        if chemists:
            for chem in chemists:
                st.write(f"• {chem['name']} ({chem.get('shop_name', 'N/A')})")
        else:
            st.info("No chemists in these territories")
    
    # ========================================
    # SECTION 6: DCR VISIT HISTORY
    # ========================================
    with st.expander("📊 DCR VISIT HISTORY (Last 30 Days)", expanded=True):
        if visits:
            # Statistics
            total_visits = len(visits)
            total_gifts = sum(1 for v in visits if v.get('gift_amount', 0) > 0)
            total_gift_value = sum(v.get('gift_amount', 0) for v in visits)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Visits", total_visits)
            with col2:
                st.metric("Gifts Given", total_gifts)
            with col3:
                st.metric("Gift Value", f"₹{total_gift_value:,.0f}")
            
            st.write("---")
            st.write("**Recent Visits:**")
            
            # Show visit details
            for visit in visits[:10]:  # Show last 10
                dcr = visit.get('dcr_reports', {})
                visit_date = dcr.get('report_date', 'N/A')
                username = dcr.get('users', {}).get('username', 'Unknown')
                
                # Get product names from product_ids JSON
                product_ids = visit.get('product_ids', [])
                if isinstance(product_ids, str):
                    import json
                    try:
                        product_ids = json.loads(product_ids)
                    except:
                        product_ids = []
                
                # Fetch product names
                product_names = []
                if product_ids:
                    products = safe_exec(
                        admin_supabase.table("products")
                        .select("name")
                        .in_("id", product_ids),
                        "Error loading products"
                    )
                    product_names = [p['name'] for p in products]
                
                st.write(f"**📅 {visit_date}** by {username}")
                if product_names:
                    st.write(f"   💊 Products: {', '.join(product_names)}")
                st.write(f"   👥 Visited with: {visit.get('visited_with', 'Single')}")
                st.write("")
        else:
            st.info("No visits in the last 30 days")
    
    # ========================================
    # SECTION 7: REMARKS HISTORY
    # ========================================
    with st.expander("📝 REMARKS HISTORY", expanded=False):
        if remarks:
            for remark in remarks:
                username = remark.get('users', {}).get('username', 'Unknown')
                added_date = remark['added_at'][:10]
                st.write(f"**{added_date}** by {username}:")
                st.write(f"   {remark['remark_text']}")
                st.write("")
        else:
            st.info("No remarks recorded yet")

def calculate_days_to_next_occurrence(event_date):
    """
    Calculate days until next occurrence of an annual event (birthday/anniversary)
    """
    today = date.today()
    this_year_event = event_date.replace(year=today.year)
    
    if this_year_event < today:
        # Event already passed this year, calculate for next year
        next_event = event_date.replace(year=today.year + 1)
    else:
        next_event = this_year_event
    
    days_until = (next_event - today).days
    return days_until
