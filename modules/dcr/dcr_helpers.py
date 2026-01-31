"""
DCR Helper Functions
Utility functions for validation, formatting, etc.
"""

import streamlit as st
from datetime import date
from modules.dcr.dcr_database import get_dcr_by_id


def get_current_user_id():
    """
    Get current logged-in user's ID
    Works with both TEST_MODE and production auth
    """
    user = st.session_state.get("auth_user")
    
    # Handle object with .id attribute
    if user and hasattr(user, "id"):
        return user.id
    
    # Handle dict with "id" key (TEST_MODE)
    if user and isinstance(user, dict) and "id" in user:
        return user["id"]
    
    # If not authenticated
    st.error("❌ User not authenticated. Please login first.")
    st.stop()


def validate_date(selected_date):
    """
    Validate DCR date
    Returns (is_valid, error_message)
    """
    if selected_date > date.today():
        return False, "Cannot create DCR for future date"
    
    return True, None


def format_whatsapp_message(dcr_id):
    """
    Format DCR data into WhatsApp message
    Returns formatted text string
    """
    dcr_data = get_dcr_by_id(dcr_id)
    
    if not dcr_data:
        return "DCR data not found"
    
    message = f"""📞 *Daily Call Report*

📅 Date: {dcr_data['report_date']}
📍 Area: {dcr_data['area_type']}
"""
    
    # Territories
    if dcr_data.get('territory_names'):
        message += f"🗺️ Territories: {', '.join(dcr_data['territory_names'])}\n"
    
    # Doctors
    doctor_visits = dcr_data.get('doctor_visits', [])
    message += f"\n👨‍⚕️ Doctors Visited: {len(doctor_visits)}\n"
    for visit in doctor_visits:
        message += f"• Dr. {visit['doctor_name']}\n"
        message += f"  Products: {', '.join(visit['product_names'])}\n"
    
    # Chemists
    chemist_names = dcr_data.get('chemist_names', [])
    message += f"\n🏪 Chemists Visited: {len(chemist_names)}\n"
    for name in chemist_names:
        message += f"• {name}\n"
    
    # Gifts
    gifts = dcr_data.get('gifts', [])
    if gifts:
        total_gift = sum(g['gift_amount'] for g in gifts)
        message += f"\n🎁 Gifts: ₹{total_gift}\n"
        for gift in gifts:
            message += f"• Dr. {gift['doctor_name']}: {gift['gift_description']} (₹{gift['gift_amount']})\n"
    
    # Expenses
    message += f"\n💰 Expenses:\n"
    message += f"🚗 KM: {dcr_data.get('km_travelled', 0)}\n"
    message += f"💸 Misc: ₹{dcr_data.get('misc_expense', 0)}\n"
    
    if dcr_data.get('misc_expense_details'):
        message += f"📝 Details: {dcr_data['misc_expense_details']}\n"
    
    return message
