"""
Doctor Input / Output Database Module
Handles all DB operations for Doctor Input (gifts) and Output (sales)

Tables used:
  - admin_input   : gift records (from company/admin directly, NOT from DCR)
  - dcr_gifts     : gifts entered during daily call report (read-only here)
  - input_output  : monthly sales/output reported by field staff
"""

import json
from datetime import datetime
import streamlit as st
from anchors.supabase_client import admin_supabase, safe_exec


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_user_territories(user_id):
    """Return [{id, name}] for territories assigned to user."""
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


def get_doctors_for_user(user_id):
    """
    Return [{id, name, specialization}] for doctors in the user's territories.
    """
    territories = get_user_territories(user_id)
    territory_ids = [t["id"] for t in territories]
    if not territory_ids:
        return []

    result = safe_exec(
        admin_supabase.table("doctor_territories")
        .select("doctors(id, name, specialization)")
        .in_("territory_id", territory_ids),
        "Error loading doctors"
    )

    seen = {}
    for r in result:
        doc = r.get("doctors")
        if doc and doc["id"] not in seen:
            seen[doc["id"]] = doc
    return list(seen.values())


def get_all_users_active():
    """Return [{id, username}] of all active users (for admin)."""
    return safe_exec(
        admin_supabase.table("users")
        .select("id, username")
        .eq("is_active", True)
        .order("username"),
        "Error loading users"
    )


def _get_doctor_name(doctor_id):
    """Helper to get a doctor's name for audit log messages."""
    try:
        result = safe_exec(
            admin_supabase.table("doctors").select("name").eq("id", doctor_id).limit(1),
            "Error loading doctor name"
        )
        return result[0]["name"] if result else "Unknown Doctor"
    except Exception:
        return "Unknown Doctor"


# ─────────────────────────────────────────────────────────────────────────────
# FORM A  –  INPUT (gifts given directly by company / admin)
# ─────────────────────────────────────────────────────────────────────────────

def save_admin_input(user_id, doctor_id, input_date, gift_description, gift_amount, amount_kind, remarks, created_by):
    """
    Insert one row into admin_input table.
    amount_kind  : 'cash' | 'kind'
    Returns inserted row id or None.
    """
    territories = get_user_territories(user_id)
    territory_ids = [t["id"] for t in territories]

    data = {
        "user_id": user_id,
        "doctor_id": doctor_id,
        "date": str(input_date),
        "month": input_date.month,
        "year": input_date.year,
        "gift_description": gift_description,
        "gift_amount": float(gift_amount),
        "remarks": f"[{amount_kind.upper()}] {remarks}" if remarks else f"[{amount_kind.upper()}]",
        "territory_ids": json.dumps(territory_ids),
        "created_by": created_by
    }

    result = safe_exec(
        admin_supabase.table("admin_input").insert(data),
        "Error saving input record"
    )

    if result:
        record_id = result[0]["id"]
        doctor_name = _get_doctor_name(doctor_id)
        # Audit log
        safe_exec(
            admin_supabase.table("audit_logs").insert({
                "action": "DOCTOR_INPUT_SAVED",
                "target_type": "admin_input",
                "target_id": record_id,
                "performed_by": created_by,
                "message": f"Doctor input saved — Dr. {doctor_name} | ₹{gift_amount} ({amount_kind.upper()}) | {gift_description}"
            }),
            "Error creating audit log"
        )
        return record_id
    return None


def update_admin_input(record_id, gift_description, gift_amount, amount_kind, remarks):
    """Update an existing admin_input row."""
    safe_exec(
        admin_supabase.table("admin_input")
        .update({
            "gift_description": gift_description,
            "gift_amount": float(gift_amount),
            "remarks": f"[{amount_kind.upper()}] {remarks}" if remarks else f"[{amount_kind.upper()}]",
        })
        .eq("id", record_id),
        "Error updating input record"
    )
    # Audit log — use the session user if available
    try:
        user = st.session_state.get("auth_user")
        performed_by = user.id if user and hasattr(user, "id") else None
    except Exception:
        performed_by = None

    safe_exec(
        admin_supabase.table("audit_logs").insert({
            "action": "DOCTOR_INPUT_UPDATED",
            "target_type": "admin_input",
            "target_id": record_id,
            "performed_by": performed_by,
            "message": f"Doctor input updated — ₹{gift_amount} ({amount_kind.upper()}) | {gift_description}"
        }),
        "Error creating audit log"
    )


def delete_admin_input(record_id):
    """Hard delete an admin_input row (no soft-delete column exists)."""
    # Fetch record info before deleting for audit log
    try:
        rec = safe_exec(
            admin_supabase.table("admin_input")
            .select("doctor_id, gift_description, gift_amount")
            .eq("id", record_id)
            .limit(1),
            "Error fetching record for audit"
        )
        if rec:
            doctor_name = _get_doctor_name(rec[0]["doctor_id"])
            msg = f"Doctor input deleted — Dr. {doctor_name} | ₹{rec[0]['gift_amount']} | {rec[0]['gift_description']}"
        else:
            msg = f"Doctor input deleted (record id: {record_id})"
    except Exception:
        msg = f"Doctor input deleted (record id: {record_id})"

    safe_exec(
        admin_supabase.table("admin_input")
        .delete()
        .eq("id", record_id),
        "Error deleting input record"
    )

    # Audit log
    try:
        user = st.session_state.get("auth_user")
        performed_by = user.id if user and hasattr(user, "id") else None
    except Exception:
        performed_by = None

    safe_exec(
        admin_supabase.table("audit_logs").insert({
            "action": "DOCTOR_INPUT_DELETED",
            "target_type": "admin_input",
            "target_id": record_id,
            "performed_by": performed_by,
            "message": msg
        }),
        "Error creating audit log"
    )


def load_admin_input_session(user_id, month, year):
    """
    Load admin_input rows for a user in a given month/year.
    Returns [{id, doctor_id, doctor_name, date, gift_description,
              gift_amount, amount_kind, remarks}]
    """
    rows = safe_exec(
        admin_supabase.table("admin_input")
        .select("*, doctors(name)")
        .eq("user_id", user_id)
        .eq("month", month)
        .eq("year", year)
        .order("date"),
        "Error loading input records"
    )

    result = []
    for r in rows:
        remarks_raw = r.get("remarks") or ""
        if remarks_raw.startswith("[CASH]"):
            amount_kind = "cash"
            remarks = remarks_raw[6:].strip()
        elif remarks_raw.startswith("[KIND]"):
            amount_kind = "kind"
            remarks = remarks_raw[6:].strip()
        else:
            amount_kind = "cash"
            remarks = remarks_raw

        result.append({
            "id": r["id"],
            "doctor_id": r["doctor_id"],
            "doctor_name": r["doctors"]["name"] if r.get("doctors") else "Unknown",
            "date": r["date"],
            "gift_description": r.get("gift_description", ""),
            "gift_amount": float(r.get("gift_amount", 0)),
            "amount_kind": amount_kind,
            "remarks": remarks
        })
    return result


def load_dcr_gifts_for_user_month(user_id, month, year):
    """
    Pull gifts already entered via the daily DCR for this user/month.
    Returns [{doctor_name, gift_description, gift_amount, report_date}]
    """
    reports = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("id, report_date")
        .eq("user_id", user_id)
        .eq("month", month)
        .eq("year", year)
        .eq("is_deleted", False),
        "Error loading DCR reports"
    )

    if not reports:
        return []

    report_ids = [r["id"] for r in reports]
    date_map = {r["id"]: r["report_date"] for r in reports}

    gifts = safe_exec(
        admin_supabase.table("dcr_gifts")
        .select("*, doctors(name)")
        .in_("dcr_report_id", report_ids),
        "Error loading DCR gifts"
    )

    result = []
    for g in gifts:
        result.append({
            "doctor_name": g["doctors"]["name"] if g.get("doctors") else "Unknown",
            "gift_description": g.get("gift_description", ""),
            "gift_amount": float(g.get("gift_amount", 0)),
            "report_date": date_map.get(g["dcr_report_id"], ""),
            "source": "DCR"
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# FORM B  –  OUTPUT (monthly sales reported by field staff)
# ─────────────────────────────────────────────────────────────────────────────

def save_doctor_output(user_id, doctor_id, month, year, sales_amount, remarks, created_by):
    """
    Upsert a row into input_output table.
    Returns row id or None.
    """
    existing = safe_exec(
        admin_supabase.table("input_output")
        .select("id")
        .eq("user_id", user_id)
        .eq("doctor_id", doctor_id)
        .eq("month", month)
        .eq("year", year),
        "Error checking existing output"
    )

    data = {
        "user_id": user_id,
        "doctor_id": doctor_id,
        "month": month,
        "year": year,
        "sales_amount": float(sales_amount),
        "remarks": remarks,
        "updated_at": datetime.utcnow().isoformat()
    }

    doctor_name = _get_doctor_name(doctor_id)

    if existing:
        row_id = existing[0]["id"]
        safe_exec(
            admin_supabase.table("input_output")
            .update(data)
            .eq("id", row_id),
            "Error updating output"
        )
        # Audit log for update
        safe_exec(
            admin_supabase.table("audit_logs").insert({
                "action": "DOCTOR_OUTPUT_SAVED",
                "target_type": "input_output",
                "target_id": row_id,
                "performed_by": created_by,
                "message": f"Doctor output saved — Dr. {doctor_name} | ₹{sales_amount} sales"
            }),
            "Error creating audit log"
        )
        return row_id
    else:
        data["created_by"] = created_by
        result = safe_exec(
            admin_supabase.table("input_output").insert(data),
            "Error saving output"
        )
        if result:
            row_id = result[0]["id"]
            # Audit log for insert
            safe_exec(
                admin_supabase.table("audit_logs").insert({
                    "action": "DOCTOR_OUTPUT_SAVED",
                    "target_type": "input_output",
                    "target_id": row_id,
                    "performed_by": created_by,
                    "message": f"Doctor output saved — Dr. {doctor_name} | ₹{sales_amount} sales"
                }),
                "Error creating audit log"
            )
            return row_id
    return None


def load_output_session(user_id, month, year):
    """
    Load output rows for a user in a given month/year.
    Returns [{id, doctor_id, doctor_name, sales_amount, remarks}]
    """
    rows = safe_exec(
        admin_supabase.table("input_output")
        .select("*, doctors(name)")
        .eq("user_id", user_id)
        .eq("month", month)
        .eq("year", year),
        "Error loading output records"
    )

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "doctor_id": r["doctor_id"],
            "doctor_name": r["doctors"]["name"] if r.get("doctors") else "Unknown",
            "sales_amount": float(r.get("sales_amount", 0)),
            "remarks": r.get("remarks", "")
        })
    return result


def delete_output_record(record_id):
    """Delete an output record."""
    # Fetch info before deleting for audit log
    try:
        rec = safe_exec(
            admin_supabase.table("input_output")
            .select("doctor_id, sales_amount")
            .eq("id", record_id)
            .limit(1),
            "Error fetching record for audit"
        )
        if rec:
            doctor_name = _get_doctor_name(rec[0]["doctor_id"])
            msg = f"Doctor output deleted — Dr. {doctor_name} | ₹{rec[0]['sales_amount']}"
        else:
            msg = f"Doctor output deleted (record id: {record_id})"
    except Exception:
        msg = f"Doctor output deleted (record id: {record_id})"

    safe_exec(
        admin_supabase.table("input_output")
        .delete()
        .eq("id", record_id),
        "Error deleting output record"
    )

    # Audit log
    try:
        user = st.session_state.get("auth_user")
        performed_by = user.id if user and hasattr(user, "id") else None
    except Exception:
        performed_by = None

    safe_exec(
        admin_supabase.table("audit_logs").insert({
            "action": "DOCTOR_OUTPUT_DELETED",
            "target_type": "input_output",
            "target_id": record_id,
            "performed_by": performed_by,
            "message": msg
        }),
        "Error creating audit log"
    )


# ─────────────────────────────────────────────────────────────────────────────
# REPORT  –  combined input + output view
# ─────────────────────────────────────────────────────────────────────────────

def load_io_report(user_id, year, months=None):
    """
    Load combined Input/Output report for a user.
    months: list of int, or None for all 12.
    """
    if months is None:
        months = list(range(1, 13))

    report = {}

    # --- Load admin_input ---
    admin_rows = safe_exec(
        admin_supabase.table("admin_input")
        .select("*, doctors(name)")
        .eq("user_id", user_id)
        .eq("year", year)
        .in_("month", months),
        "Error loading input for report"
    )

    for r in admin_rows:
        did = r["doctor_id"]
        dname = r["doctors"]["name"] if r.get("doctors") else "Unknown"
        mo = r["month"]
        remarks = r.get("remarks") or ""
        amount = float(r.get("gift_amount", 0))

        if did not in report:
            report[did] = {"doctor_name": dname, "data": {}}
        key = (mo, year)
        if key not in report[did]["data"]:
            report[did]["data"][key] = _empty_cell()
        if "[KIND]" in remarks.upper():
            report[did]["data"][key]["input_kind"] += amount
        else:
            report[did]["data"][key]["input_cash"] += amount

    # --- Load DCR gifts ---
    dcr_reports = safe_exec(
        admin_supabase.table("dcr_reports")
        .select("id, month")
        .eq("user_id", user_id)
        .eq("year", year)
        .in_("month", months)
        .eq("is_deleted", False),
        "Error loading DCR reports for IO"
    )

    if dcr_reports:
        rpt_ids = [r["id"] for r in dcr_reports]
        month_map = {r["id"]: r["month"] for r in dcr_reports}

        gifts = safe_exec(
            admin_supabase.table("dcr_gifts")
            .select("*, doctors(name)")
            .in_("dcr_report_id", rpt_ids),
            "Error loading DCR gifts for IO"
        )

        for g in gifts:
            did = g["doctor_id"]
            dname = g["doctors"]["name"] if g.get("doctors") else "Unknown"
            mo = month_map.get(g["dcr_report_id"], 0)
            amount = float(g.get("gift_amount", 0))

            if did not in report:
                report[did] = {"doctor_name": dname, "data": {}}
            key = (mo, year)
            if key not in report[did]["data"]:
                report[did]["data"][key] = _empty_cell()
            report[did]["data"][key]["dcr_gift"] += amount

    # --- Load output ---
    output_rows = safe_exec(
        admin_supabase.table("input_output")
        .select("*, doctors(name)")
        .eq("user_id", user_id)
        .eq("year", year)
        .in_("month", months),
        "Error loading output for report"
    )

    for r in output_rows:
        did = r["doctor_id"]
        dname = r["doctors"]["name"] if r.get("doctors") else "Unknown"
        mo = r["month"]
        amount = float(r.get("sales_amount", 0))

        if did not in report:
            report[did] = {"doctor_name": dname, "data": {}}
        key = (mo, year)
        if key not in report[did]["data"]:
            report[did]["data"][key] = _empty_cell()
        report[did]["data"][key]["output"] += amount

    # Compute totals
    for did in report:
        for key in report[did]["data"]:
            cell = report[did]["data"][key]
            cell["total_input"] = cell["input_cash"] + cell["input_kind"] + cell["dcr_gift"]

    return report


def _empty_cell():
    return {"input_cash": 0.0, "input_kind": 0.0, "dcr_gift": 0.0,
            "total_input": 0.0, "output": 0.0}
