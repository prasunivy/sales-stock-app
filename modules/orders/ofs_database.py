"""
Order From Stockist — Database Module
Tables: ofs_orders, ofs_order_lines
"""

import streamlit as st
from datetime import datetime
from anchors.supabase_client import admin_supabase


# ─────────────────────────────────────────────────────────────
# SAFE EXEC
# ─────────────────────────────────────────────────────────────

def _exec(query, err="Database error"):
    try:
        resp = query.execute()
        return resp.data or []
    except Exception as e:
        st.error(f"❌ {err}: {str(e)}")
        return []


# ─────────────────────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────────────────────

def ofs_get_user_stockists(user_id: str) -> list:
    """Return stockists linked to user via user_stockists table."""
    rows = _exec(
        admin_supabase.table("user_stockists")
        .select("stockist_id, stockists(id, name, location)")
        .eq("user_id", str(user_id)),
        "Error loading stockists"
    )
    result = []
    for r in rows:
        s = r.get("stockists")
        if s:
            result.append(s)
    return result


def ofs_get_all_products() -> list:
    rows = _exec(
        admin_supabase.table("products")
        .select("id, name")
        .order("name"),
        "Error loading products"
    )
    return rows


# ─────────────────────────────────────────────────────────────
# ORDER NUMBER GENERATOR
# ─────────────────────────────────────────────────────────────

def ofs_generate_order_no() -> str:
    """Generate next OFS order number e.g. OFS-001.
    Uses existing pob_number_sequences table with doc_type = 'OFS'."""
    try:
        rows = _exec(
            admin_supabase.table("pob_number_sequences")
            .select("last_number")
            .eq("doc_type", "OFS"),
            "Error reading OFS sequence"
        )
        if not rows:
            st.error("OFS sequence row missing. Run the SQL setup script first.")
            import time
            return f"OFS-{int(time.time())}"
        current = rows[0]["last_number"]
        next_no = current + 1
        admin_supabase.table("pob_number_sequences") \
            .update({"last_number": next_no}) \
            .eq("doc_type", "OFS") \
            .execute()
        return f"OFS-{str(next_no).zfill(3)}"
    except Exception as e:
        import time
        st.error(f"Error generating order number: {e}")
        return f"OFS-{int(time.time())}"


# ─────────────────────────────────────────────────────────────
# ORDER CRUD
# ─────────────────────────────────────────────────────────────

def ofs_create_order(user_id, stockist_id, order_date) -> str:
    """Create a new draft order. Returns order id."""
    order_no = ofs_generate_order_no()
    rows = _exec(
        admin_supabase.table("ofs_orders").insert({
            "order_no":   order_no,
            "user_id":    user_id,
            "stockist_id": stockist_id,
            "order_date": str(order_date),
            "status":     "draft",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }),
        "Error creating order"
    )
    return rows[0]["id"] if rows else None


def ofs_load_order(order_id) -> dict:
    """Load order header."""
    rows = _exec(
        admin_supabase.table("ofs_orders")
        .select("*, stockists(name)")
        .eq("id", order_id)
        .limit(1),
        "Error loading order"
    )
    if not rows:
        return {}
    o = rows[0]
    o["stockist_name"] = o.get("stockists", {}).get("name", "Unknown") if o.get("stockists") else "Unknown"
    return o


def ofs_submit_order(order_id, user_id) -> bool:
    """Mark order as submitted."""
    _exec(
        admin_supabase.table("ofs_orders").update({
            "status":       "submitted",
            "submitted_at": datetime.utcnow().isoformat(),
            "updated_at":   datetime.utcnow().isoformat(),
        }).eq("id", order_id),
        "Error submitting order"
    )
    # Audit log
    _exec(
        admin_supabase.table("audit_logs").insert({
            "action":      "OFS_SUBMITTED",
            "target_type": "ofs_orders",
            "target_id":   order_id,
            "performed_by": user_id,
            "message":     f"Order From Stockist submitted"
        }),
        "Error writing audit log"
    )
    return True


def ofs_delete_order(order_id, user_id) -> bool:
    """Soft delete order."""
    _exec(
        admin_supabase.table("ofs_orders").update({
            "is_deleted":  True,
            "deleted_at":  datetime.utcnow().isoformat(),
            "deleted_by":  user_id,
            "updated_at":  datetime.utcnow().isoformat(),
        }).eq("id", order_id),
        "Error deleting order"
    )
    _exec(
        admin_supabase.table("audit_logs").insert({
            "action":      "OFS_DELETED",
            "target_type": "ofs_orders",
            "target_id":   order_id,
            "performed_by": user_id,
            "message":     "Order From Stockist deleted"
        }),
        "Error writing audit log"
    )
    return True


# ─────────────────────────────────────────────────────────────
# ORDER LINES CRUD
# ─────────────────────────────────────────────────────────────

def ofs_save_line(order_id, product_id, product_name, seq_no,
                  sale_qty, free_qty, discount, discount_type) -> str:
    """Insert or update a line. Returns line id."""
    # Check if line already exists for this product
    existing = _exec(
        admin_supabase.table("ofs_order_lines")
        .select("id")
        .eq("order_id", order_id)
        .eq("product_id", product_id),
        "Error checking existing line"
    )
    data = {
        "order_id":      order_id,
        "product_id":    product_id,
        "product_name":  product_name,
        "seq_no":        seq_no,
        "sale_qty":      int(sale_qty),
        "free_qty":      int(free_qty),
        "discount":      float(discount),
        "discount_type": discount_type,
        "updated_at":    datetime.utcnow().isoformat(),
    }
    if existing:
        line_id = existing[0]["id"]
        _exec(
            admin_supabase.table("ofs_order_lines")
            .update(data)
            .eq("id", line_id),
            "Error updating line"
        )
        return line_id
    else:
        data["created_at"] = datetime.utcnow().isoformat()
        rows = _exec(
            admin_supabase.table("ofs_order_lines").insert(data),
            "Error saving line"
        )
        return rows[0]["id"] if rows else None


def ofs_delete_line(line_id) -> bool:
    _exec(
        admin_supabase.table("ofs_order_lines")
        .delete()
        .eq("id", line_id),
        "Error deleting line"
    )
    return True


def ofs_load_lines(order_id) -> list:
    """Load all lines for an order, sorted by seq_no."""
    rows = _exec(
        admin_supabase.table("ofs_order_lines")
        .select("*")
        .eq("order_id", order_id)
        .order("seq_no"),
        "Error loading lines"
    )
    return rows


# ─────────────────────────────────────────────────────────────
# ARCHIVE / HISTORY
# ─────────────────────────────────────────────────────────────

def ofs_load_archive(user_id, role, stockist_filter=None,
                     status_filter="ALL", limit=50) -> list:
    """Load order history. Admin sees all, user sees own."""
    query = (
        admin_supabase.table("ofs_orders")
        .select("*, stockists(name), users!ofs_orders_user_id_fkey(username)")
        .eq("is_deleted", False)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if role != "admin":
        query = query.eq("user_id", user_id)
    if stockist_filter:
        query = query.eq("stockist_id", stockist_filter)
    if status_filter != "ALL":
        query = query.eq("status", status_filter)

    rows = _exec(query, "Error loading archive")
    for r in rows:
        r["stockist_name"] = r.get("stockists", {}).get("name", "Unknown") if r.get("stockists") else "Unknown"
        r["username"]      = r.get("users!ofs_orders_user_id_fkey", {}).get("username", "Unknown") if r.get("users!ofs_orders_user_id_fkey") else "Unknown"
    return rows


# ─────────────────────────────────────────────────────────────
# WHATSAPP FORMAT
# ─────────────────────────────────────────────────────────────

def ofs_format_whatsapp(order: dict, lines: list) -> str:
    """Format order as WhatsApp message."""
    msg  = f"📦 *Order From Stockist*\n"
    msg += f"Order No: *{order.get('order_no', 'N/A')}*\n"
    msg += f"Date: {order.get('order_date', 'N/A')}\n"
    msg += f"Stockist: *{order.get('stockist_name', 'N/A')}*\n"
    msg += f"─────────────────\n"

    for i, line in enumerate(lines, 1):
        disc_label = "on MRP" if line.get("discount_type") == "ON_MRP" else "on Invoice"
        msg += f"{i}. *{line['product_name']}*\n"
        msg += f"   Sale Qty: {line['sale_qty']}  Free: {line['free_qty']}\n"
        if line.get("discount", 0) > 0:
            msg += f"   Discount: {line['discount']}% ({disc_label})\n"

    msg += f"─────────────────\n"
    msg += f"Total Products: {len(lines)}\n"
    msg += f"Total Sale Qty: {sum(l['sale_qty'] for l in lines)}\n"
    return msg
