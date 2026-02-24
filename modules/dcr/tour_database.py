"""
Tour Programme Database Operations
Handles all CRUD operations for tour programmes
"""

from anchors.supabase_client import admin_supabase, safe_exec
from datetime import datetime
import json


def get_tour_programmes_list(user_id, status_filter=None, search=None):
    """Get list of tour programmes for a user"""
    # Build query step by step
    
    query = admin_supabase.table("tour_programmes").select("id, tour_date, territory_ids, worked_with_type, notes, status, approved_by, approved_at, approval_comment, created_at, user_id").eq("user_id", user_id).is_("deleted_at", None)
    
    if status_filter:
        query = query.eq("status", status_filter)
    
    if search:
        query = query.ilike("notes", f"%{search}%")
    
    tours = safe_exec(query.order("tour_date", desc=True), "Error loading tours")
    
    if not tours:
        return []
    
    # Enrich with territory names and counts
    for tour in tours:
        territory_ids = tour.get('territory_ids', [])
        if isinstance(territory_ids, str):
            territory_ids = json.loads(territory_ids)
        
        if territory_ids:
            territories = safe_exec(
                admin_supabase.table("territories").select("name").in_("id", territory_ids),
                "Error loading territory names"
            )
            tour['territory_names'] = [t['name'] for t in territories]
        else:
            tour['territory_names'] = []
        
        doctor_count = safe_exec(
            admin_supabase.table("tour_programme_doctors").select("id").eq("tour_programme_id", tour['id']),
            "Error counting doctors"
        )
        tour['doctor_count'] = len(doctor_count)
        
        chemist_count = safe_exec(
            admin_supabase.table("tour_programme_chemists").select("id").eq("tour_programme_id", tour['id']),
            "Error counting chemists"
        )
        tour['chemist_count'] = len(chemist_count)
        tour['approver_name'] = None
    
    return tours

def get_tour_by_id(tour_id):
    """Get complete tour programme details"""
    tour = safe_exec(
        admin_supabase.table("tour_programmes").select("*").eq("id", tour_id).limit(1),
        "Error loading tour"
    )
    
    if not tour:
        return None
    
    tour_data = tour[0]
    territory_ids = tour_data.get('territory_ids', [])
    if isinstance(territory_ids, str):
        territory_ids = json.loads(territory_ids)
    tour_data['territory_ids'] = territory_ids
    
    if territory_ids:
        territories = safe_exec(
            admin_supabase.table("territories").select("id, name").in_("id", territory_ids),
            "Error loading territories"
        )
        tour_data['territories'] = territories
    else:
        tour_data['territories'] = []
    
    tour_doctors = safe_exec(
        admin_supabase.table("tour_programme_doctors").select("doctor_id").eq("tour_programme_id", tour_id),
        "Error loading tour doctors"
    )
    tour_data['doctor_ids'] = [td['doctor_id'] for td in tour_doctors]
    tour_data['doctors'] = []
    
    tour_chemists = safe_exec(
        admin_supabase.table("tour_programme_chemists").select("chemist_id").eq("tour_programme_id", tour_id),
        "Error loading tour chemists"
    )
    tour_data['chemist_ids'] = [tc['chemist_id'] for tc in tour_chemists]
    tour_data['chemists'] = []
    tour_data['approver_name'] = None
    
    return tour_data


def create_tour_programme(user_id, tour_date, territory_ids, worked_with_type, doctor_ids, chemist_ids, notes, status):
    """Create new tour programme"""
    tour = safe_exec(
        admin_supabase.table("tour_programmes").insert({
            "user_id": user_id,
            "tour_date": str(tour_date),
            "territory_ids": json.dumps(territory_ids),
            "worked_with_type": worked_with_type,
            "notes": notes,
            "status": status,
            "created_at": datetime.now().isoformat()
        }),
        "Error creating tour programme"
    )
    if not tour:
        raise Exception("Failed to create tour programme")
    
    tour_id = tour[0]['id']
    
    if doctor_ids:
        for doctor_id in doctor_ids:
            safe_exec(
                admin_supabase.table("tour_programme_doctors").insert({
                    "tour_programme_id": tour_id,
                    "doctor_id": doctor_id
                }),
                "Error adding doctor"
            )
    
    if chemist_ids:
        for chemist_id in chemist_ids:
            safe_exec(
                admin_supabase.table("tour_programme_chemists").insert({
                    "tour_programme_id": tour_id,
                    "chemist_id": chemist_id
                }),
                "Error adding chemist"
            )
    
    return tour_id


def update_tour_programme(tour_id, tour_date, territory_ids, worked_with_type, doctor_ids, chemist_ids, notes, status):
    """Update existing tour programme"""
    safe_exec(
        admin_supabase.table("tour_programmes").update({
            "tour_date": str(tour_date),
            "territory_ids": json.dumps(territory_ids),
            "worked_with_type": worked_with_type,
            "notes": notes,
            "status": status,
            "updated_at": datetime.now().isoformat()
        }).eq("id", tour_id),
        "Error updating tour"
    )
    
    safe_exec(admin_supabase.table("tour_programme_doctors").delete().eq("tour_programme_id", tour_id), "Error removing old doctors")
    safe_exec(admin_supabase.table("tour_programme_chemists").delete().eq("tour_programme_id", tour_id), "Error removing old chemists")
    
    if doctor_ids:
        for doctor_id in doctor_ids:
            safe_exec(admin_supabase.table("tour_programme_doctors").insert({"tour_programme_id": tour_id, "doctor_id": doctor_id}), "Error adding doctor")
    
    if chemist_ids:
        for chemist_id in chemist_ids:
            safe_exec(admin_supabase.table("tour_programme_chemists").insert({"tour_programme_id": tour_id, "chemist_id": chemist_id}), "Error adding chemist")


def delete_tour_programme(tour_id):
    """Soft delete tour programme"""
    safe_exec(
        admin_supabase.table("tour_programmes").update({"deleted_at": datetime.now().isoformat()}).eq("id", tour_id),
        "Error deleting tour"
    )


def get_doctors_by_territories(territory_ids):
    """Get doctors in given territories"""
    if not territory_ids:
        return []
    
    result = safe_exec(
        admin_supabase.table("doctor_territories").select("doctors(id, name, specialization)").in_("territory_id", territory_ids),
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
    """Get chemists in given territories"""
    if not territory_ids:
        return []
    
    result = safe_exec(
        admin_supabase.table("chemists").select("id, name, shop_name").in_("territory_id", territory_ids).eq("is_active", True).order("name"),
        "Error loading chemists"
    )
    
    return result
