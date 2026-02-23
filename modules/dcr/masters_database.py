"""
Masters Database Operations
Handles all database queries for doctors and chemists masters
"""

import streamlit as st
from anchors.supabase_client import admin_supabase, safe_exec


# ======================================================
# COMMON / HELPER FUNCTIONS
# ======================================================

def get_user_territories(user_id):
    """
    Get territories assigned to a user
    Returns list of {id, name}
    """
    result = safe_exec(
        admin_supabase.table("user_territories")
        .select("territory_id, territories(id, name)")
        .eq("user_id", user_id),
        "Error loading user territories"
    )
    
    territories = []
    for r in result:
        if r.get("territories"):
            territories.append({
                "id": r["territories"]["id"],
                "name": r["territories"]["name"]
            })
    
    return territories


def get_all_users():
    """
    Get all active users (for admin)
    Returns list of {id, username}
    """
    result = safe_exec(
        admin_supabase.table("users")
        .select("id, username")
        .eq("is_active", True)
        .order("username"),
        "Error loading users"
    )
    return result


def get_stockists_by_territories(territory_ids):
    """
    Get stockists for given territories
    Returns list of {id, name}
    """
    if not territory_ids:
        return []
    
    result = safe_exec(
        admin_supabase.table("territory_stockists")
        .select("stockist_id, stockists(id, name)")
        .in_("territory_id", territory_ids),
        "Error loading stockists"
    )
    
    # Remove duplicates
    stockists = {}
    for r in result:
        if r.get("stockists"):
            sid = r["stockists"]["id"]
            if sid not in stockists:
                stockists[sid] = {
                    "id": sid,
                    "name": r["stockists"]["name"]
                }
    
    return list(stockists.values())


def get_stockist_by_territory(territory_id):
    """
    Get THE stockist for a territory (single)
    Returns {id, name} or None
    """
    result = safe_exec(
        admin_supabase.table("territory_stockists")
        .select("stockist_id, stockists(id, name)")
        .eq("territory_id", territory_id)
        .limit(1),
        "Error loading stockist"
    )
    
    if result and result[0].get("stockists"):
        return {
            "id": result[0]["stockists"]["id"],
            "name": result[0]["stockists"]["name"]
        }
    return None


def get_chemists_by_territories(territory_ids):
    """
    Get chemists for given territories
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


# ======================================================
# DOCTORS CRUD
# ======================================================

def get_doctors_list(user_id, search=None, territory_id=None, active_only=True):
    """
    Get list of doctors for a user
    Filtered by search, territory, active status
    """
    # Get user's territories
    user_territory_ids = [t['id'] for t in get_user_territories(user_id)]
    
    if not user_territory_ids:
        return []
    
    # Build query
    query = admin_supabase.table("doctors").select("""
        id,
        name,
        specialization,
        phone,
        clinic_address,
        is_active
    """)
    
    if active_only:
        query = query.eq("is_active", True)
    
    if search:
        query = query.ilike("name", f"%{search}%")
    
    doctors = safe_exec(query.order("name"), "Error loading doctors")
    
    # Filter by user's territories and enrich with territory/stockist info
    result = []
    for doctor in doctors:
        # Get doctor's territories
        doc_territories = safe_exec(
            admin_supabase.table("doctor_territories")
            .select("territory_id, territories(id, name)")
            .eq("doctor_id", doctor['id']),
            "Error loading doctor territories"
        )
        
        doctor_territory_ids = [dt['territory_id'] for dt in doc_territories]
        
        # Check if doctor belongs to any of user's territories
        if not any(tid in user_territory_ids for tid in doctor_territory_ids):
            continue
        
        # If territory filter is set, check if doctor is in that territory
        if territory_id and territory_id not in doctor_territory_ids:
            continue
        
        # Get territory names
        territory_names = [dt['territories']['name'] for dt in doc_territories if dt.get('territories')]
        
        # Get stockists
        doc_stockists = safe_exec(
            admin_supabase.table("doctor_stockists")
            .select("stockist_id, stockists(name)")
            .eq("doctor_id", doctor['id']),
            "Error loading doctor stockists"
        )
        stockist_names = [ds['stockists']['name'] for ds in doc_stockists if ds.get('stockists')]
        
        # Get chemist count
        # Note: We'll need to create a doctor_chemists linking table
        # For now, return 0
        chemist_ids = []  # TODO: Implement when table exists
        
        doctor['territory_names'] = territory_names
        doctor['territory_ids'] = doctor_territory_ids
        doctor['stockist_names'] = stockist_names
        doctor['chemist_ids'] = chemist_ids
        
        result.append(doctor)
    
    return result


def get_doctor_by_id(doctor_id):
    """
    Get single doctor with all details
    """
    doctor = safe_exec(
        admin_supabase.table("doctors")
        .select("*")
        .eq("id", doctor_id)
        .limit(1),
        "Error loading doctor"
    )
    
    if not doctor:
        return None
    
    doc = doctor[0]
    
    # Get territories
    doc_territories = safe_exec(
        admin_supabase.table("doctor_territories")
        .select("territory_id, territories(id, name)")
        .eq("doctor_id", doctor_id),
        "Error loading territories"
    )
    
    doc['territory_ids'] = [dt['territory_id'] for dt in doc_territories]
    doc['territory_names'] = [dt['territories']['name'] for dt in doc_territories if dt.get('territories')]
    
    # Get stockists
    doc_stockists = safe_exec(
        admin_supabase.table("doctor_stockists")
        .select("stockist_id, stockists(name)")
        .eq("doctor_id", doctor_id),
        "Error loading stockists"
    )
    
    doc['stockist_ids'] = [ds['stockist_id'] for ds in doc_stockists]
    doc['stockist_names'] = [ds['stockists']['name'] for ds in doc_stockists if ds.get('stockists')]
    
    # Get chemists (TODO: when table exists)
    doc['chemist_ids'] = []
    
    return doc


def create_doctor(name, specialization, phone, clinic_address, territory_ids, stockist_ids, chemist_ids, created_by):
    """
    Create new doctor with all relationships
    """
    # Insert doctor
    doctor = safe_exec(
        admin_supabase.table("doctors").insert({
            "name": name,
            "specialization": specialization,
            "phone": phone,
            "clinic_address": clinic_address,
            "is_active": True,
            "created_by": created_by
        }),
        "Error creating doctor"
    )
    
    if not doctor:
        raise Exception("Failed to create doctor")
    
    doctor_id = doctor[0]['id']    
    # Link territories
    for territory_id in territory_ids:
        safe_exec(
            admin_supabase.table("doctor_territories").insert({
                "doctor_id": doctor_id,
                "territory_id": territory_id,
                "assigned_by": created_by
            }),
            "Error linking territory"
        )
    
    # Link stockists
    for stockist_id in stockist_ids:
        safe_exec(
            admin_supabase.table("doctor_stockists").insert({
                "doctor_id": doctor_id,
                "stockist_id": stockist_id,
                "assigned_by": created_by
            }),
            "Error linking stockist"
        )
    
    # TODO: Link chemists when table exists
    
    return doctor_id


def update_doctor(doctor_id, name, specialization, phone, clinic_address, stockist_ids, chemist_ids, updated_by):
    """
    Update doctor (territories cannot be changed)
    """
    # Update basic info
    safe_exec(
        admin_supabase.table("doctors").update({
            "name": name,
            "specialization": specialization,
            "phone": phone,
            "clinic_address": clinic_address,
            "updated_by": updated_by
        }).eq("id", doctor_id),
        "Error updating doctor"
    )
    
    # Update stockists - delete all and re-add
    safe_exec(
        admin_supabase.table("doctor_stockists")
        .delete()
        .eq("doctor_id", doctor_id),
        "Error deleting old stockists"
    )
    
    for stockist_id in stockist_ids:
        safe_exec(
            admin_supabase.table("doctor_stockists").insert({
                "doctor_id": doctor_id,
                "stockist_id": stockist_id,
                "assigned_by": updated_by
            }),
            "Error linking stockist"
        )
    
    # TODO: Update chemists when table exists


def delete_doctor_soft(doctor_id, deleted_by):
    """
    Soft delete doctor (set is_active = false)
    """
    safe_exec(
        admin_supabase.table("doctors").update({
            "is_active": False,
            "updated_by": deleted_by
        }).eq("id", doctor_id),
        "Error deleting doctor"
    )


# ======================================================
# CHEMISTS CRUD
# ======================================================

def get_chemists_list(user_id, search=None, territory_id=None, active_only=True):
    """
    Get list of chemists for a user
    """
    # Get user's territories
    user_territory_ids = [t['id'] for t in get_user_territories(user_id)]
    
    if not user_territory_ids:
        return []
    
    # Build query
    query = admin_supabase.table("chemists").select("""
        id,
        name,
        shop_name,
        phone,
        address,
        territory_id,
        stockist_id,
        is_active,
        territories(name),
        stockists(name)
    """)
    
    if active_only:
        query = query.eq("is_active", True)
    
    if territory_id:
        query = query.eq("territory_id", territory_id)
    else:
        query = query.in_("territory_id", user_territory_ids)
    
    if search:
        query = query.or_(f"name.ilike.%{search}%,shop_name.ilike.%{search}%")
    
    chemists = safe_exec(query.order("name"), "Error loading chemists")
    
    # Enrich with territory/stockist names
    for chemist in chemists:
        chemist['territory_name'] = chemist.get('territories', {}).get('name', 'N/A')
        chemist['stockist_name'] = chemist.get('stockists', {}).get('name', 'N/A')
    
    return chemists


def get_chemist_by_id(chemist_id):
    """
    Get single chemist with all details
    """
    chemist = safe_exec(
        admin_supabase.table("chemists")
        .select("""
            *,
            territories(name),
            stockists(name)
        """)
        .eq("id", chemist_id)
        .limit(1),
        "Error loading chemist"
    )
    
    if not chemist:
        return None
    
    chem = chemist[0]
    chem['territory_name'] = chem.get('territories', {}).get('name', 'N/A')
    chem['stockist_name'] = chem.get('stockists', {}).get('name', 'N/A')
    
    return chem


def create_chemist(name, shop_name, phone, address, territory_id, stockist_id, created_by):
    """
    Create new chemist
    """
    chemist = safe_exec(
        admin_supabase.table("chemists").insert({
            "name": name,
            "shop_name": shop_name,
            "phone": phone,
            "address": address,
            "territory_id": territory_id,
            "stockist_id": stockist_id,
            "is_active": True,
            "created_by": created_by
        }),
        "Error creating chemist"
    )
    
    if not chemist:
        raise Exception("Failed to create chemist")
    
    return chemist[0]['id']

def update_chemist(chemist_id, name, shop_name, phone, address, updated_by):
    """
    Update chemist (territory and stockist cannot be changed)
    """
    safe_exec(
        admin_supabase.table("chemists").update({
            "name": name,
            "shop_name": shop_name,
            "phone": phone,
            "address": address,
            "updated_by": updated_by
        }).eq("id", chemist_id),
        "Error updating chemist"
    )


def delete_chemist_soft(chemist_id, deleted_by):
    """
    Soft delete chemist (set is_active = false)
    """
    safe_exec(
        admin_supabase.table("chemists").update({
            "is_active": False,
            "updated_by": deleted_by
        }).eq("id", chemist_id),
        "Error deleting chemist"
    )
