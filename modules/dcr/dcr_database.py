"""
DCR Database Module
Handles all database operations for DCR
"""

import streamlit as st
from datetime import datetime
import json
from anchors.supabase_client import admin_supabase


def init_dcr_session_state():
    """
    Initialize all DCR session state keys
    Called once at module entry
    """
    defaults = {
        "dcr_report_id": None,
        "dcr_current_step": 1,
        "dcr_user_id": None,
        "dcr_report_date": None,
        "dcr_area_type": None,
        "dcr_territory_ids": [],
        "dcr_submit_done": False,
        "dcr_delete_confirm": False,
        "dcr_home_action": None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def safe_exec(query, error_msg="Database error"):
    """
    Safely execute Supabase query with error handling
    Returns data or empty list on error
    """
    try:
        response = query.execute()
        return response.data if response.data else []
    except Exception as e:
        st.error(f"{error_msg}: {str(e)}")
        return []


def check_duplicate_dcr(user_id, report_date):
    """
    Check if DCR already exists for user on this date
    Returns True if duplicate exists
    """
    result = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("id")
        .eq("user_id", user_id)
        .eq("report_date", str(report_date))
        .eq("is_deleted", False),
        "Error checking duplicate DCR"
    )
    return len(result) > 0


def create_dcr_draft(user_id, report_date, area_type, territory_ids, created_by):
    """
    Create new DCR draft record
    Returns DCR ID
    """
    data = {
        "user_id": user_id,
        "report_date": str(report_date),
        "month": report_date.month,
        "year": report_date.year,
        "area_type": area_type,
        "territory_ids": json.dumps(territory_ids) if territory_ids else None,
        "status": "draft",
        "current_step": 1,
        "created_by": created_by
    }
    
    result = safe_exec(
        admin_supabase.table("dcr_reports").insert(data),
        "Error creating DCR draft"
    )
    
    if result:
        return result[0]["id"]
    return None


def save_dcr_header(dcr_id, area_type, territory_ids):
    """
    Update DCR header (stage 1 data)
    """
    data = {
        "area_type": area_type,
        "territory_ids": json.dumps(territory_ids) if territory_ids else None,
        "current_step": 1,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    safe_exec(
        admin_supabase.table("dcr_reports")
        .update(data)
        .eq("id", dcr_id),
        "Error saving DCR header"
    )


def save_doctor_visit(dcr_id, doctor_id, product_ids, visited_with):
    """
    Add a doctor visit to DCR
    """
    # Get next sequence number
    existing = safe_exec(
        admin_supabase.table("dcr_doctor_visits")
        .select("sequence_no")
        .eq("dcr_report_id", dcr_id)
        .order("sequence_no", desc=True)
        .limit(1),
        "Error getting visit sequence"
    )
    
    next_seq = (existing[0]["sequence_no"] + 1) if existing else 1
    
    data = {
        "dcr_report_id": dcr_id,
        "doctor_id": doctor_id,
        "product_ids": json.dumps(product_ids),
        "visited_with": visited_with,
        "sequence_no": next_seq
    }
    
    safe_exec(
        admin_supabase.table("dcr_doctor_visits").insert(data),
        "Error saving doctor visit"
    )


def remove_doctor_visit(visit_id):
    """
    Remove a doctor visit
    """
    safe_exec(
        admin_supabase.table("dcr_doctor_visits")
        .delete()
        .eq("id", visit_id),
        "Error removing doctor visit"
    )


def save_chemist_visits(dcr_id, chemist_ids):
    """
    Save chemist IDs to DCR (as JSONB array)
    """
    data = {
        "chemist_ids": json.dumps(chemist_ids) if chemist_ids else None,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    safe_exec(
        admin_supabase.table("dcr_reports")
        .update(data)
        .eq("id", dcr_id),
        "Error saving chemist visits"
    )


def save_gift(dcr_id, doctor_id, gift_description, gift_amount):
    """
    Add a gift record
    """
    # Get next sequence number
    existing = safe_exec(
        admin_supabase.table("dcr_gifts")
        .select("sequence_no")
        .eq("dcr_report_id", dcr_id)
        .order("sequence_no", desc=True)
        .limit(1),
        "Error getting gift sequence"
    )
    
    next_seq = (existing[0]["sequence_no"] + 1) if existing else 1
    
    data = {
        "dcr_report_id": dcr_id,
        "doctor_id": doctor_id,
        "gift_description": gift_description,
        "gift_amount": gift_amount,
        "sequence_no": next_seq
    }
    
    safe_exec(
        admin_supabase.table("dcr_gifts").insert(data),
        "Error saving gift"
    )


def remove_gift(gift_id):
    """
    Remove a gift record
    """
    safe_exec(
        admin_supabase.table("dcr_gifts")
        .delete()
        .eq("id", gift_id),
        "Error removing gift"
    )


def save_expenses(dcr_id, km_travelled, misc_expense, misc_expense_details):
    """
    Save expense data (stage 3)
    """
    data = {
        "km_travelled": km_travelled,
        "misc_expense": misc_expense,
        "misc_expense_details": misc_expense_details,
        "current_step": 3,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    safe_exec(
        admin_supabase.table("dcr_reports")
        .update(data)
        .eq("id", dcr_id),
        "Error saving expenses"
    )


def submit_dcr_final(dcr_id, submitted_by):
    """
    Mark DCR as submitted (final)
    """
    data = {
        "status": "submitted",
        "submitted_at": datetime.utcnow().isoformat(),
        "is_locked": True,
        "locked_at": datetime.utcnow().isoformat(),
        "locked_by": submitted_by,
        "current_step": 4,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    safe_exec(
        admin_supabase.table("dcr_reports")
        .update(data)
        .eq("id", dcr_id),
        "Error submitting DCR"
    )
    
    # Audit log
    safe_exec(
        admin_supabase.table("audit_logs").insert({
            "action": "DCR_SUBMITTED",
            "target_type": "dcr_reports",
            "target_id": dcr_id,
            "performed_by": submitted_by,
            "message": "Daily Call Report submitted"
        }),
        "Error creating audit log"
    )


def delete_dcr_soft(dcr_id, deleted_by):
    """
    Soft delete DCR (set is_deleted flag)
    """
    data = {
        "is_deleted": True,
        "deleted_at": datetime.utcnow().isoformat(),
        "deleted_by": deleted_by
    }
    
    safe_exec(
        admin_supabase.table("dcr_reports")
        .update(data)
        .eq("id", dcr_id),
        "Error deleting DCR"
    )

    # Audit log
    safe_exec(
        admin_supabase.table("audit_logs").insert({
            "action": "DCR_DELETED",
            "target_type": "dcr_reports",
            "target_id": dcr_id,
            "performed_by": deleted_by,
            "message": "Daily Call Report deleted"
        }),
        "Error creating audit log"
    )


def get_dcr_by_id(dcr_id):
    """
    Load complete DCR data with all related records
    Returns dict with all DCR information
    """
    # Validate dcr_id
    if not dcr_id or dcr_id == "None" or str(dcr_id) == "None":
        return {}
        
    # Get main record
    dcr = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("*")
        .eq("id", dcr_id)
        .limit(1),
        "Error loading DCR"
    )
    
    if not dcr:
        return {}
    
    dcr_data = dcr[0]
    
    # Parse JSONB fields safely
    try:
        territory_ids = json.loads(dcr_data.get("territory_ids") or "[]")
    except:
        territory_ids = []

    try:
        chemist_ids = json.loads(dcr_data.get("chemist_ids") or "[]")
    except:
        chemist_ids = []

    # Ensure they're lists
    if not isinstance(territory_ids, list):
        territory_ids = []
    if not isinstance(chemist_ids, list):
        chemist_ids = []
    
    # Get territory names
    territory_names = []
    if territory_ids:
        territories = safe_exec(
            admin_supabase.table("territories")
            .select("name")
            .in_("id", territory_ids),
            "Error loading territories"
        )
        territory_names = [t["name"] for t in territories]
    
    # Get chemist names
    chemist_names = []
    if chemist_ids:
        chemists = safe_exec(
            admin_supabase.table("chemists")
            .select("name")
            .in_("id", chemist_ids),
            "Error loading chemists"
        )
        chemist_names = [c["name"] for c in chemists]
    
    # Get doctor visits
    visits = safe_exec(
        admin_supabase.table("dcr_doctor_visits")
        .select("*, doctors(name)")
        .eq("dcr_report_id", dcr_id)
        .order("sequence_no"),
        "Error loading doctor visits"
    )
    
    doctor_visits = []
    for visit in visits:
        product_ids = json.loads(visit.get("product_ids") or "[]")
        
        # Get product names
        product_names = []
        if product_ids:
            products = safe_exec(
                admin_supabase.table("products")
                .select("name")
                .in_("id", product_ids),
                "Error loading products"
            )
            product_names = [p["name"] for p in products]
        
        doctor_visits.append({
            "id": visit["id"],
            "doctor_id": visit["doctor_id"],
            "doctor_name": visit["doctors"]["name"],
            "product_ids": product_ids,
            "product_names": product_names,
            "visited_with": visit.get("visited_with", "single"),
            "sequence_no": visit["sequence_no"]
        })
    
    # Get gifts
    gifts = safe_exec(
        admin_supabase.table("dcr_gifts")
        .select("*, doctors(name)")
        .eq("dcr_report_id", dcr_id)
        .order("sequence_no"),
        "Error loading gifts"
    )
    
    gift_list = []
    for gift in gifts:
        gift_list.append({
            "id": gift["id"],
            "doctor_id": gift["doctor_id"],
            "doctor_name": gift["doctors"]["name"],
            "gift_description": gift["gift_description"],
            "gift_amount": gift["gift_amount"],
            "sequence_no": gift["sequence_no"]
        })
    
    # Compile complete data
    dcr_data["territory_names"] = territory_names
    dcr_data["chemist_names"] = chemist_names
    dcr_data["doctor_visits"] = doctor_visits
    dcr_data["gifts"] = gift_list
    
    return dcr_data


def get_user_territories(user_id):
    """
    Get territories assigned to user
    Returns list of {id, name}
    """
    try:
        result = safe_exec(
            admin_supabase.table("user_territories")
            .select("territory_id, territories(id, name)")
            .eq("user_id", user_id),
            "Error loading user territories"
        )
        
        # Extract territories from nested structure
        territories = []
        for r in result:
            if r.get("territories"):
                territories.append({
                    "id": r["territories"]["id"],
                    "name": r["territories"]["name"]
                })
        
        return territories
    
    except Exception as e:
        st.error(f"Error in get_user_territories: {str(e)}")
        return []

def get_doctors_by_territories(territory_ids):
    """
    Get doctors practicing in given territories
    Returns list of {id, name, specialization}
    """
    if not territory_ids:
        return []
    
    result = safe_exec(
        admin_supabase.table("doctor_territories")
        .select("doctors(id, name, specialization)")
        .in_("territory_id", territory_ids),
        "Error loading doctors"
    )
    
    # Remove duplicates
    doctors_dict = {}
    for r in result:
        if r.get("doctors"):
            doc = r["doctors"]
            doctors_dict[doc["id"]] = doc
    
    return list(doctors_dict.values())


def get_chemists_by_territories(territory_ids):
    """
    Get chemists in given territories
    Returns list of {id, name, shop_name}
    """
    if not territory_ids:
        return []
    
    result = safe_exec(
        admin_supabase.table("chemists")
        .select("id, name, shop_name")
        .in_("territory_id", territory_ids)
        .eq("is_active", True)
        .order("name"),
        "Error loading chemists"
    )
    
    return result


def get_products_all():
    """
    Get all active products
    Returns list of {id, name}
    """
    result = safe_exec(
        admin_supabase.table("products")
        .select("id, name")
        .order("name"),
        "Error loading products"
    )
    
    return result


def get_managers_list():
    """
    Get list of managers and admins for "visited with" dropdown
    Returns list of {id, username, designation}
    """
    result = safe_exec(
        admin_supabase.table("users")
        .select("id, username, designation, role")
        .in_("designation", ["manager", "senior_manager"])
        .eq("is_active", True)
        .order("username"),
        "Error loading managers"
    )
    
    # Also add admins
    admins = safe_exec(
        admin_supabase.table("users")
        .select("id, username, designation, role")
        .eq("role", "admin")
        .eq("is_active", True)
        .order("username"),
        "Error loading admins"
    )
    
    return result + admins


def load_dcr_monthly_reports(user_id, year, month):
    """
    Load all DCRs for user in given month/year
    Returns list of DCR summaries
    """
    result = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("*")
        .eq("user_id", user_id)
        .eq("year", year)
        .eq("month", month)
        .eq("is_deleted", False)
        .order("report_date"),
        "Error loading monthly reports"
    )
    
    # Add counts for each report
    for report in result:
        # Count doctor visits
        doc_count = safe_exec(
            admin_supabase.table("dcr_doctor_visits")
            .select("id", count="exact")
            .eq("dcr_report_id", report["id"]),
            "Error counting doctors"
        )
        report["doctor_count"] = len(doc_count)
        
        # Count chemists
        chemist_ids = json.loads(report.get("chemist_ids") or "[]")
        report["chemist_count"] = len(chemist_ids)
        
        # Count gifts
        gift_count = safe_exec(
            admin_supabase.table("dcr_gifts")
            .select("id", count="exact")
            .eq("dcr_report_id", report["id"]),
            "Error counting gifts"
        )
        report["gift_count"] = len(gift_count)
    
    return result
