"""
Doctor Fetch Module
Allows users to update doctor details, view 360 degree profiles,
and capture GPS locations for doctors.
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

    # ── Restore GPS + doctor state from URL params if GPS triggered a reload ──
    # This must run FIRST before any routing logic
    params = st.query_params
    if "gps_lat" in params and "gps_long" in params:
        try:
            st.session_state.gps_lat     = float(params["gps_lat"])
            st.session_state.gps_long    = float(params["gps_long"])
            st.session_state.gps_fetched = True
        except Exception:
            pass
        if "gps_doc_id" in params:
            st.session_state.doctor_fetch_doctor_id = params["gps_doc_id"]
        if "gps_terr_id" in params:
            st.session_state.doctor_fetch_territory = params["gps_terr_id"]
        if "gps_mode" in params:
            st.session_state.doctor_fetch_mode = params["gps_mode"]
        st.query_params.clear()

    # Show options
    if "doctor_fetch_mode" not in st.session_state:
        st.session_state.doctor_fetch_mode = None

    if not st.session_state.doctor_fetch_mode:
        show_doctor_fetch_home()
    elif st.session_state.doctor_fetch_mode == "UPDATE":
        show_update_doctor_flow()
    elif st.session_state.doctor_fetch_mode == "FETCH":
        show_fetch_doctor_flow()
    elif st.session_state.doctor_fetch_mode == "CAPTURE":
        show_capture_location_flow()


# ══════════════════════════════════════════════════════════════
# HOME SCREEN
# ══════════════════════════════════════════════════════════════

def show_doctor_fetch_home():
    """
    Home screen with Update / Fetch / Capture Location options
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

    st.write("")
    if st.button("📍 Capture Location", use_container_width=True, type="primary"):
        # Clear any stale GPS state before starting fresh
        st.session_state.gps_lat     = 0.0
        st.session_state.gps_long    = 0.0
        st.session_state.gps_fetched = False
        st.session_state.doctor_fetch_mode = "CAPTURE"
        st.rerun()

    st.write("")
    if st.button("🏠 Back to DCR Home"):
        st.session_state.engine_stage = "dcr"
        st.session_state.doctor_fetch_mode = None
        for key in ["doctor_fetch_territory", "doctor_fetch_doctor_id",
                    "gps_lat", "gps_long", "gps_fetched"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()


# ══════════════════════════════════════════════════════════════
# UPDATE DOCTOR FLOW
# (DOB, Anniversary, Remarks, View + Delete Locations)
# ══════════════════════════════════════════════════════════════

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
    Form to update doctor details:
    - DOB and Anniversary (fill once, then locked)
    - Remarks (add any time)
    - View and Delete existing locations
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

    # ── Special Dates ─────────────────────────────────────────
    st.write("#### 📅 Special Dates")

    if doc.get("date_of_birth"):
        st.text_input("Date of Birth", value=str(doc["date_of_birth"]),
                      disabled=True, help="Already saved - cannot edit")
        new_dob = None
    else:
        new_dob = st.date_input("Date of Birth (Optional)", value=None)

    if doc.get("date_of_anniversary"):
        st.text_input("Date of Anniversary", value=str(doc["date_of_anniversary"]),
                      disabled=True, help="Already saved - cannot edit")
        new_doa = None
    else:
        new_doa = st.date_input("Date of Anniversary (Optional)", value=None)

    st.write("---")

    # ── Existing Locations (view + delete) ────────────────────
    st.write("#### 📍 Saved Locations")

    existing_locations = safe_exec(
        admin_supabase.table("doctor_locations")
        .select("*")
        .eq("doctor_id", doctor_id)
        .eq("is_active", True)
        .order("added_at"),
        "Error loading locations"
    ) or []

    if not existing_locations:
        st.info("No locations saved yet. Use 📍 Capture Location from the home screen to add one.")
    else:
        st.caption(f"{len(existing_locations)}/3 locations saved")
        for idx, loc in enumerate(existing_locations):
            col_info, col_del = st.columns([4, 1])
            with col_info:
                st.markdown(
                    f"<div style='background:#f0faf7;border-left:4px solid #1a6b5a;"
                    f"padding:0.5rem 0.8rem;border-radius:6px;margin-bottom:4px;"
                    f"font-size:0.87rem;'>"
                    f"<b>{idx+1}. {loc['location_name']}</b><br>"
                    f"<span style='color:#5a7268;'>📍 {loc['latitude']}, {loc['longitude']}"
                    f" &nbsp;·&nbsp; Added: {loc['added_at'][:10]}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_del:
                if st.button("🗑️", key=f"del_loc_{loc['id']}",
                             help="Delete this location"):
                    if st.session_state.get(f"confirm_del_loc_{loc['id']}"):
                        safe_exec(
                            admin_supabase.table("doctor_locations")
                            .update({"is_active": False})
                            .eq("id", loc["id"]),
                            "Error deleting location"
                        )
                        st.success("Location deleted.")
                        st.session_state.pop(f"confirm_del_loc_{loc['id']}", None)
                        st.rerun()
                    else:
                        st.session_state[f"confirm_del_loc_{loc['id']}"] = True
                        st.warning("Tap 🗑️ again to confirm")

    if len(existing_locations) < 3:
        st.caption("👉 Use **📍 Capture Location** from the home screen to add a new location.")

    st.write("---")

    # ── Remarks ───────────────────────────────────────────────
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

    new_remark = st.text_area(
        "Add New Remark (Optional)",
        placeholder="Enter your notes about this doctor"
    )

    st.write("---")

    # ── Save Changes button ───────────────────────────────────
    if st.button("💾 Save Changes", type="primary"):
        current_user_id = get_current_user_id()
        saved_something = False

        if new_dob:
            safe_exec(
                admin_supabase.table("doctors")
                .update({"date_of_birth": str(new_dob), "updated_by": current_user_id})
                .eq("id", doctor_id),
                "Error updating DOB"
            )
            saved_something = True

        if new_doa:
            safe_exec(
                admin_supabase.table("doctors")
                .update({"date_of_anniversary": str(new_doa), "updated_by": current_user_id})
                .eq("id", doctor_id),
                "Error updating DOA"
            )
            saved_something = True

        if new_remark and new_remark.strip():
            safe_exec(
                admin_supabase.table("doctor_remarks").insert({
                    "doctor_id": doctor_id,
                    "remark_text": new_remark.strip(),
                    "added_by": current_user_id
                }),
                "Error adding remark"
            )
            saved_something = True

        if saved_something:
            st.success("✅ Doctor details updated successfully!")
        else:
            st.info("Nothing to save — no changes made.")

        del st.session_state.doctor_fetch_territory
        del st.session_state.doctor_fetch_doctor_id
        st.session_state.doctor_fetch_mode = None
        st.rerun()

    if st.button("❌ Cancel"):
        del st.session_state.doctor_fetch_territory
        del st.session_state.doctor_fetch_doctor_id
        st.session_state.doctor_fetch_mode = None
        st.rerun()


# ══════════════════════════════════════════════════════════════
# CAPTURE LOCATION FLOW
# Step 1: GPS Fetch
# Step 2: Select Territory
# Step 3: Select Doctor → Save
# ══════════════════════════════════════════════════════════════

def show_capture_location_flow():
    """
    Capture GPS location and link it to a doctor.
    Step 1: Fetch GPS → coordinates shown on screen → user enters them → Save & Next
    Step 2: Select Territory
    Step 3: Select Doctor → Save
    """
    st.write("### 📍 Capture Location")

    import streamlit.components.v1 as components

    # Initialize GPS state
    if "gps_lat" not in st.session_state:
        st.session_state.gps_lat = 0.0
    if "gps_long" not in st.session_state:
        st.session_state.gps_long = 0.0
    if "gps_fetched" not in st.session_state:
        st.session_state.gps_fetched = False

    # ── STEP 1: GPS Fetch ─────────────────────────────────────
    if not st.session_state.gps_fetched:
        st.info("📌 **Step 1 of 3** — Stand at the doctor's location. "
                "Click the button below to get your GPS coordinates, "
                "then enter them in the boxes that appear and click **Save & Next**.")

        # JavaScript fetches GPS and displays coords in a large clear box
        # No redirect needed — user copies the values into the Streamlit inputs below
        components.html("""
            <style>
                #gps-btn {
                    background-color: #1a6b5a;
                    color: white;
                    border: none;
                    padding: 16px 20px;
                    font-size: 16px;
                    border-radius: 8px;
                    cursor: pointer;
                    width: 100%;
                }
                #gps-btn:hover { background-color: #145249; }
                #gps-btn:disabled { background-color: #888; cursor: not-allowed; }
                #gps-result {
                    display: none;
                    background: #d4edda;
                    border: 2px solid #1a6b5a;
                    border-radius: 10px;
                    padding: 16px;
                    margin-top: 14px;
                }
                #gps-result .label {
                    font-size: 13px;
                    color: #155724;
                    margin-bottom: 10px;
                    font-weight: 600;
                    text-align: center;
                }
                .coord-row {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    background: white;
                    border-radius: 8px;
                    padding: 10px 14px;
                    margin-bottom: 8px;
                }
                .coord-label {
                    font-size: 13px;
                    color: #5a7268;
                    font-weight: 600;
                    width: 40px;
                }
                .coord-value {
                    font-size: 18px;
                    font-weight: bold;
                    color: #1a6b5a;
                    flex: 1;
                    text-align: center;
                    letter-spacing: 0.5px;
                }
                .copy-btn {
                    background: #1a6b5a;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 13px;
                    cursor: pointer;
                    white-space: nowrap;
                }
                .copy-btn:hover { background: #145249; }
                .copy-btn.copied { background: #28a745; }
                #gps-result .instruction {
                    font-size: 13px;
                    color: #155724;
                    margin-top: 8px;
                    text-align: center;
                }
                #gps-status {
                    font-size: 13px;
                    margin-top: 10px;
                    font-weight: bold;
                    min-height: 20px;
                }
            </style>

            <button id="gps-btn" onclick="fetchGPS()">📍 Fetch My Current Location</button>
            <div id="gps-status"></div>

            <div id="gps-result">
                <div class="label">✅ GPS Coordinates Captured — tap 📋 Copy then paste into the box below</div>

                <div class="coord-row">
                    <span class="coord-label">Lat</span>
                    <span class="coord-value" id="lat-display">—</span>
                    <button class="copy-btn" id="copy-lat-btn" onclick="copyCoord('lat-display','copy-lat-btn')">📋 Copy</button>
                </div>

                <div class="coord-row">
                    <span class="coord-label">Long</span>
                    <span class="coord-value" id="long-display">—</span>
                    <button class="copy-btn" id="copy-long-btn" onclick="copyCoord('long-display','copy-long-btn')">📋 Copy</button>
                </div>

                <div class="instruction">
                    👇 Paste each value into the Latitude / Longitude boxes below, then click <b>Save & Next</b>
                </div>
            </div>

            <script>
            function copyCoord(spanId, btnId) {
                var text = document.getElementById(spanId).innerText;
                var btn  = document.getElementById(btnId);
                navigator.clipboard.writeText(text).then(function() {
                    btn.innerText = '✅ Copied!';
                    btn.classList.add('copied');
                    setTimeout(function() {
                        btn.innerText = '📋 Copy';
                        btn.classList.remove('copied');
                    }, 2000);
                }).catch(function() {
                    // Fallback for older browsers
                    var el = document.createElement('textarea');
                    el.value = text;
                    document.body.appendChild(el);
                    el.select();
                    document.execCommand('copy');
                    document.body.removeChild(el);
                    btn.innerText = '✅ Copied!';
                    btn.classList.add('copied');
                    setTimeout(function() {
                        btn.innerText = '📋 Copy';
                        btn.classList.remove('copied');
                    }, 2000);
                });
            }

            function fetchGPS() {
                var btn    = document.getElementById('gps-btn');
                var status = document.getElementById('gps-status');
                var result = document.getElementById('gps-result');

                btn.disabled  = true;
                btn.innerText = '⏳ Fetching GPS... (may take 10-20 sec)';
                status.style.color = '#333';
                status.innerText   = 'Waiting for GPS signal...';
                result.style.display = 'none';

                if (!navigator.geolocation) {
                    status.style.color = '#c0392b';
                    status.innerText   = '❌ GPS not supported on this browser.';
                    btn.disabled  = false;
                    btn.innerText = '📍 Fetch My Current Location';
                    return;
                }

                navigator.geolocation.getCurrentPosition(
                    function(pos) {
                        var lat = pos.coords.latitude.toFixed(6);
                        var lon = pos.coords.longitude.toFixed(6);

                        document.getElementById('lat-display').innerText  = lat;
                        document.getElementById('long-display').innerText = lon;
                        result.style.display = 'block';

                        status.style.color = '#1a6b5a';
                        status.innerText   = '✅ Done! Copy each value and paste into the boxes below.';
                        btn.disabled  = false;
                        btn.innerText = '🔄 Fetch Again';
                    },
                    function(err) {
                        var msgs = {
                            1: '❌ Permission denied. Go to Settings > Browser > Location and allow access.',
                            2: '❌ GPS unavailable. Move to an open area and try again.',
                            3: '❌ Timed out. Please try again.'
                        };
                        status.style.color = '#c0392b';
                        status.innerText   = msgs[err.code] || '❌ GPS error: ' + err.message;
                        btn.disabled  = false;
                        btn.innerText = '📍 Fetch My Current Location';
                    },
                    { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
                );
            }
            </script>
        """, height=340)

        st.write("")
        st.write("**Enter coordinates shown above:**")

        col1, col2 = st.columns(2)
        with col1:
            entered_lat = st.number_input(
                "Latitude", format="%.6f",
                value=0.0, step=0.000001,
                key="capture_lat_input"
            )
        with col2:
            entered_long = st.number_input(
                "Longitude", format="%.6f",
                value=0.0, step=0.000001,
                key="capture_long_input"
            )

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Save & Next ➡️", type="primary", key="capture_coords_next"):
                if entered_lat == 0.0 and entered_long == 0.0:
                    st.error("❌ Please fetch GPS and enter the coordinates first.")
                else:
                    st.session_state.gps_lat     = entered_lat
                    st.session_state.gps_long    = entered_long
                    st.session_state.gps_fetched = True
                    st.rerun()
        with col_b:
            if st.button("⬅️ Back to Home", key="capture_back_step1"):
                st.session_state.doctor_fetch_mode = None
                st.rerun()
        return

    # ── Coordinates captured — show them ─────────────────────
    st.success(
        f"✅ **GPS Captured** — "
        f"Lat: `{st.session_state.gps_lat:.6f}` | "
        f"Long: `{st.session_state.gps_long:.6f}`"
    )

    # ── STEP 2: Territory selection ───────────────────────────
    if "doctor_fetch_territory" not in st.session_state:
        st.info("📌 Step 2 of 3 — Select the territory where this doctor is located.")

        user_id = get_current_user_id()
        territories = get_user_territories(user_id)

        if not territories:
            st.warning("No territories assigned to you.")
            if st.button("⬅️ Back", key="capture_back_no_terr"):
                st.session_state.gps_fetched = False
                st.rerun()
            return

        selected_territory = st.selectbox(
            "Select Territory",
            options=[t["id"] for t in territories],
            format_func=lambda x: next(t["name"] for t in territories if t["id"] == x),
            key="capture_territory_select"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Next ➡️", type="primary", key="capture_territory_next"):
                st.session_state.doctor_fetch_territory = selected_territory
                st.rerun()
        with col2:
            if st.button("⬅️ Back", key="capture_back_step2"):
                st.session_state.gps_fetched = False
                st.rerun()
        return

    # ── STEP 3: Doctor selection + Location name + Save ───────
    st.info("📌 Step 3 of 3 — Select the doctor and enter a location name, then save.")

    territory_id = st.session_state.doctor_fetch_territory

    doctors = safe_exec(
        admin_supabase.table("doctor_territories")
        .select("doctors(id, name, specialization)")
        .eq("territory_id", territory_id),
        "Error loading doctors"
    )
    doctor_list = [d["doctors"] for d in doctors if d.get("doctors")]

    if not doctor_list:
        st.warning("No doctors found in this territory.")
        if st.button("⬅️ Back", key="capture_back_no_doctors"):
            del st.session_state.doctor_fetch_territory
            st.rerun()
        return

    selected_doctor_id = st.selectbox(
        "Select Doctor",
        options=[d["id"] for d in doctor_list],
        format_func=lambda x: next(
            f"{d['name']} ({d.get('specialization', 'N/A')})"
            for d in doctor_list if d["id"] == x
        ),
        key="capture_doctor_select"
    )

    # Check how many locations this doctor already has
    existing_count = 0
    if selected_doctor_id:
        existing_locs = safe_exec(
            admin_supabase.table("doctor_locations")
            .select("id, location_name")
            .eq("doctor_id", selected_doctor_id)
            .eq("is_active", True),
            "Error checking locations"
        ) or []
        existing_count = len(existing_locs)

        if existing_count > 0:
            st.caption(f"📍 This doctor already has {existing_count}/3 location(s) saved.")

    if existing_count >= 3:
        st.error(
            "❌ This doctor already has 3 saved locations (maximum). "
            "Go to **✏️ Update Doctor Details** to delete an existing location first."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Change Doctor", key="capture_change_doc"):
                st.rerun()
        with col2:
            if st.button("🏠 Back to Home", key="capture_home_maxloc"):
                _clear_capture_state()
                st.rerun()
        return

    # Location name input
    loc_name = st.text_input(
        "Location Name *",
        placeholder="e.g., City Hospital OPD, Main Clinic, Nursing Home",
        key="capture_loc_name"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Location", type="primary", key="capture_save"):
            if not loc_name or not loc_name.strip():
                st.error("❌ Please enter a location name.")
            else:
                current_user_id = get_current_user_id()
                safe_exec(
                    admin_supabase.table("doctor_locations").insert({
                        "doctor_id": selected_doctor_id,
                        "location_name": loc_name.strip(),
                        "latitude": st.session_state.gps_lat,
                        "longitude": st.session_state.gps_long,
                        "added_by": current_user_id
                    }),
                    "Error saving location"
                )
                # Find doctor name for confirmation message
                doc_name = next(
                    (d["name"] for d in doctor_list if d["id"] == selected_doctor_id),
                    "Doctor"
                )
                st.success(
                    f"✅ Location **'{loc_name.strip()}'** saved for "
                    f"**Dr. {doc_name}** successfully!"
                )
                _clear_capture_state()
                st.rerun()
    with col2:
        if st.button("⬅️ Change Territory", key="capture_back_step3"):
            del st.session_state.doctor_fetch_territory
            st.rerun()


def _clear_capture_state():
    """Clear all capture location session state."""
    for key in ["doctor_fetch_territory", "doctor_fetch_doctor_id",
                "gps_lat", "gps_long", "gps_fetched"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.doctor_fetch_mode = None


# ══════════════════════════════════════════════════════════════
# FETCH DOCTOR FLOW (360° Profile)
# ══════════════════════════════════════════════════════════════

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
            format_func=lambda x: next(
                f"{d['name']} ({d.get('specialization', 'N/A')})"
                for d in doctor_list if d["id"] == x
            ),
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

    # ── Load all data upfront ─────────────────────────────────
    territories = safe_exec(
        admin_supabase.table("doctor_territories")
        .select("territories(id, name)")
        .eq("doctor_id", doctor_id),
        "Error loading territories"
    ) or []
    territory_ids = [t['territories']['id'] for t in territories if t.get('territories')]

    locations = safe_exec(
        admin_supabase.table("doctor_locations")
        .select("*")
        .eq("doctor_id", doctor_id)
        .eq("is_active", True)
        .order("added_at"),
        "Error loading locations"
    ) or []

    stockists = safe_exec(
        admin_supabase.table("doctor_stockists")
        .select("stockists(name)")
        .eq("doctor_id", doctor_id),
        "Error loading stockists"
    ) or []

    chemists = []
    if territory_ids:
        chemists = safe_exec(
            admin_supabase.table("chemists")
            .select("name, shop_name")
            .in_("territory_id", territory_ids)
            .eq("is_active", True)
            .order("name"),
            "Error loading chemists"
        ) or []

    thirty_days_ago = (datetime.now() - timedelta(days=30)).date()
    recent_dcrs = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("id, report_date, user_id, users!dcr_reports_user_fkey(username)")
        .gte("report_date", str(thirty_days_ago))
        .order("report_date", desc=True),
        "Error loading recent DCRs"
    ) or []

    recent_dcr_ids = [dcr['id'] for dcr in recent_dcrs]
    visits = []
    if recent_dcr_ids:
        visits_raw = safe_exec(
            admin_supabase.table("dcr_doctor_visits")
            .select("*")
            .eq("doctor_id", doctor_id)
            .in_("dcr_report_id", recent_dcr_ids),
            "Error loading visit history"
        ) or []
        for visit in visits_raw:
            dcr = next((d for d in recent_dcrs if d['id'] == visit['dcr_report_id']), None)
            if dcr:
                visit['dcr_reports'] = dcr
                visits.append(visit)
        visits.sort(
            key=lambda x: x.get('dcr_reports', {}).get('report_date', ''),
            reverse=True
        )

    remarks = safe_exec(
        admin_supabase.table("doctor_remarks")
        .select("*, users!doctor_remarks_added_by_fkey(username)")
        .eq("doctor_id", doctor_id)
        .eq("is_deleted", False)
        .order("added_at", desc=True)
        .limit(10),
        "Error loading remarks"
    ) or []

    io_admin_input = safe_exec(
        admin_supabase.table("admin_input")
        .select("month, year, gift_amount, remarks, date")
        .eq("doctor_id", doctor_id)
        .order("year", desc=True)
        .order("month", desc=True),
        "Error loading input data"
    ) or []

    io_dcr_gifts = safe_exec(
        admin_supabase.table("dcr_gifts")
        .select("gift_amount, dcr_report_id, dcr_reports(report_date, month, year)")
        .eq("doctor_id", doctor_id)
        .order("created_at", desc=True),
        "Error loading DCR gifts"
    ) or []

    io_output = safe_exec(
        admin_supabase.table("input_output")
        .select("month, year, sales_amount, remarks")
        .eq("doctor_id", doctor_id)
        .order("year", desc=True)
        .order("month", desc=True),
        "Error loading output data"
    ) or []

    # ── Header ────────────────────────────────────────────────
    st.write(f"# 👨‍⚕️ Dr. {doc['name']}")
    st.write(f"### {doc.get('specialization', 'Specialist')}")

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

    # Section 1: Basic Information
    with st.expander("📋 BASIC INFORMATION", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**📞 Phone:** {doc.get('phone', 'N/A')}")
            st.write(f"**🏥 Clinic:** {doc.get('clinic_address', 'N/A')}")
        with col2:
            if doc.get('date_of_birth'):
                dob = datetime.strptime(str(doc['date_of_birth']), '%Y-%m-%d').date()
                days_to_birthday = calculate_days_to_next_occurrence(dob)
                emoji = "🎂" if days_to_birthday <= 30 else "📅"
                st.write(f"**{emoji} Birthday:** {dob.strftime('%b %d')} (in {days_to_birthday} days)")
            else:
                st.write("**📅 Birthday:** Not set")
            if doc.get('date_of_anniversary'):
                doa = datetime.strptime(str(doc['date_of_anniversary']), '%Y-%m-%d').date()
                days_to_ann = calculate_days_to_next_occurrence(doa)
                emoji = "💐" if days_to_ann <= 30 else "📅"
                st.write(f"**{emoji} Anniversary:** {doa.strftime('%b %d')} (in {days_to_ann} days)")
            else:
                st.write("**📅 Anniversary:** Not set")

    # Section 2: Locations
    with st.expander("📍 LOCATIONS", expanded=False):
        if locations:
            for idx, loc in enumerate(locations):
                st.write(f"**{idx+1}. {loc['location_name']}**")
                st.write(f"   📍 Coordinates: {loc['latitude']}, {loc['longitude']}")
                st.write(f"   🕒 Added: {loc['added_at'][:10]}")
                st.write("")
        else:
            st.info("No locations saved yet")

    # Section 3: Territories
    with st.expander("🗺️ TERRITORIES & COVERAGE", expanded=False):
        if territories:
            for t in territories:
                if t.get('territories'):
                    st.write(f"• {t['territories']['name']}")
        else:
            st.info("No territories assigned")

    # Section 4: Linked Stockists
    with st.expander("🏢 LINKED STOCKISTS", expanded=False):
        if stockists:
            for s in stockists:
                if s.get('stockists'):
                    st.write(f"• {s['stockists']['name']}")
        else:
            st.info("No stockists linked")

    # Section 5: Linked Chemists
    with st.expander("💊 LINKED CHEMISTS", expanded=False):
        if chemists:
            for chem in chemists:
                st.write(f"• {chem['name']} ({chem.get('shop_name', 'N/A')})")
        else:
            st.info("No chemists in these territories")

    # Section 6: DCR Visit History
    with st.expander("📊 DCR VISIT HISTORY (Last 30 Days)", expanded=True):
        if visits:
            total_visits     = len(visits)
            total_gifts      = sum(1 for v in visits if v.get('gift_amount', 0) > 0)
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
            for visit in visits[:10]:
                dcr        = visit.get('dcr_reports', {})
                visit_date = dcr.get('report_date', 'N/A')
                username   = dcr.get('users', {}).get('username', 'Unknown')
                product_ids = visit.get('product_ids', [])
                if isinstance(product_ids, str):
                    import json
                    try:
                        product_ids = json.loads(product_ids)
                    except Exception:
                        product_ids = []
                product_names = []
                if product_ids:
                    prods = safe_exec(
                        admin_supabase.table("products")
                        .select("name")
                        .in_("id", product_ids),
                        "Error loading products"
                    ) or []
                    product_names = [p['name'] for p in prods]
                st.write(f"**📅 {visit_date}** by {username}")
                if product_names:
                    st.write(f"   💊 Products: {', '.join(product_names)}")
                st.write(f"   👥 Visited with: {visit.get('visited_with', 'Single')}")
                st.write("")
        else:
            st.info("No visits in the last 30 days")

    # Section 7: Remarks
    with st.expander("📝 REMARKS HISTORY", expanded=False):
        if remarks:
            for remark in remarks:
                username   = remark.get('users', {}).get('username', 'Unknown')
                added_date = remark['added_at'][:10]
                st.write(f"**{added_date}** by {username}:")
                st.write(f"   {remark['remark_text']}")
                st.write("")
        else:
            st.info("No remarks recorded yet")

    # Section 8: Input / Output Report
    with st.expander("💊 INPUT / OUTPUT REPORT", expanded=False):
        import pandas as pd
        MONTHS = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                  7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
        io_map = {}
        for r in io_admin_input:
            key = (r["year"], r["month"])
            if key not in io_map:
                io_map[key] = {"input_direct": 0.0, "input_dcr": 0.0, "output": 0.0}
            io_map[key]["input_direct"] += float(r.get("gift_amount", 0))
        for g in io_dcr_gifts:
            dcr = g.get("dcr_reports") or {}
            yr  = dcr.get("year")
            mo  = dcr.get("month")
            if yr and mo:
                key = (yr, mo)
                if key not in io_map:
                    io_map[key] = {"input_direct": 0.0, "input_dcr": 0.0, "output": 0.0}
                io_map[key]["input_dcr"] += float(g.get("gift_amount", 0))
        for r in io_output:
            key = (r["year"], r["month"])
            if key not in io_map:
                io_map[key] = {"input_direct": 0.0, "input_dcr": 0.0, "output": 0.0}
            io_map[key]["output"] += float(r.get("sales_amount", 0))

        if not io_map:
            st.info("No input / output data recorded for this doctor yet.")
        else:
            rows = []
            for (yr, mo) in sorted(io_map.keys(), reverse=True):
                cell        = io_map[(yr, mo)]
                total_input = cell["input_direct"] + cell["input_dcr"]
                rows.append({
                    "Month":             f"{MONTHS[mo]} {yr}",
                    "Direct Input (₹)":  f"₹{cell['input_direct']:,.2f}",
                    "DCR Gift (₹)":      f"₹{cell['input_dcr']:,.2f}",
                    "Total Input (₹)":   f"₹{total_input:,.2f}",
                    "Output (₹)":        f"₹{cell['output']:,.2f}",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.write("---")
            all_direct = sum(v["input_direct"] for v in io_map.values())
            all_dcr    = sum(v["input_dcr"]    for v in io_map.values())
            all_input  = all_direct + all_dcr
            all_output = sum(v["output"]        for v in io_map.values())
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Input (All Time)",  f"₹{all_input:,.0f}")
            with col2:
                st.metric("Total Output (All Time)", f"₹{all_output:,.0f}")
            with col3:
                ratio = (all_output / all_input * 100) if all_input > 0 else 0
                st.metric("Output / Input Ratio",    f"{ratio:.1f}%")


# ══════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════

def calculate_days_to_next_occurrence(event_date):
    """
    Calculate days until next occurrence of an annual event (birthday/anniversary)
    """
    today = date.today()
    this_year_event = event_date.replace(year=today.year)
    if this_year_event < today:
        next_event = event_date.replace(year=today.year + 1)
    else:
        next_event = this_year_event
    return (next_event - today).days
