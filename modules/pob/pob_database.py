"""
POB Database Module
Handles all Supabase operations for POB / Statement / Credit Note
Tables: pob_documents, pob_lines, pob_number_sequences

Fully self-contained — no dependency on dcr_database or any other module.
"""

import streamlit as st
from datetime import datetime
from anchors.supabase_client import admin_supabase


# ─────────────────────────────────────────────────────────────
# INTERNAL SAFE EXECUTE
# ─────────────────────────────────────────────────────────────

def _exec(query, err="Database error"):
    """Safe Supabase query executor. Returns list or []."""
    try:
        resp = query.execute()
        return resp.data or []
    except Exception as e:
        st.error(f"❌ {err}: {str(e)}")
        return []


# ─────────────────────────────────────────────────────────────
# PARTY LOADERS  (chemists / stockists linked to user)
# ─────────────────────────────────────────────────────────────

def pob_get_user_territories(user_id: str) -> list:
    rows = _exec(
        admin_supabase.table("user_territories")
        .select("territory_id, territories(id, name)")
        .eq("user_id", str(user_id)),
        "Error loading territories"
    )
    result = []
    for r in rows:
        t = r.get("territories")
        if t:
            result.append({"id": t["id"], "name": t["name"]})
    return result


def pob_get_user_chemists(user_id: str) -> list:
    """Return chemists in the user's territories."""
    territories = pob_get_user_territories(user_id)
    if not territories:
        return []
    tid_list = [t["id"] for t in territories]
    rows = _exec(
        admin_supabase.table("chemists")
        .select("id, name, shop_name, territory_id")
        .in_("territory_id", tid_list)
        .eq("is_active", True)
        .order("name"),
        "Error loading chemists"
    )
    return rows or []


def pob_get_user_stockists(user_id: str) -> list:
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


def pob_get_all_products() -> list:
    rows = _exec(
        admin_supabase.table("products")
        .select("id, name")
        .order("name"),
        "Error loading products"
    )
    return rows or []


# ─────────────────────────────────────────────────────────────
# DOC NUMBER GENERATOR
# ─────────────────────────────────────────────────────────────

_PREFIX = {"POB": "POB", "STATEMENT": "STM", "CR_NT": "CRN"}

def pob_generate_doc_no(doc_type: str) -> str:
    """
    Reads pob_number_sequences, increments by 1, returns formatted number.
    e.g.  POB-0001, STM-0003, CRN-0011
    """
    try:
        resp = admin_supabase.table("pob_number_sequences") \
            .select("last_no") \
            .eq("doc_type", doc_type) \
            .single() \
            .execute()
        current = resp.data["last_no"]
        next_no = current + 1
        admin_supabase.table("pob_number_sequences") \
            .update({"last_no": next_no}) \
            .eq("doc_type", doc_type) \
            .execute()
        prefix = _PREFIX.get(doc_type, doc_type)
        return f"{prefix}-{str(next_no).zfill(4)}"
    except Exception as e:
        st.error(f"Error generating doc number: {e}")
        import time
        return f"{doc_type}-{int(time.time())}"


# ─────────────────────────────────────────────────────────────
# CALCULATIONS  (pure math, no DB)
# ─────────────────────────────────────────────────────────────

def pob_calculate_line(sale_qty, free_qty, mrp_incl_tax, tax_rate, discount) -> dict:
    """
    All values based on the formula spec:
    f = c - (c*d / (100+d))     MRP excl tax
    g = f * 0.8                  Retail price
    i = g - (g*e / 100)          Sales price
    j = i * d / 100              Tax amount
    k = i + j                    Gross rate per unit
    l = k * a                    Net rate (total for sale_qty)
    """
    c = float(mrp_incl_tax)
    d = float(tax_rate)
    e = float(discount)
    a = float(sale_qty)

    f = c - (c * d / (100 + d))   if (100 + d) != 0 else 0
    g = f * 0.8
    i = g - (g * e / 100)
    j = i * d / 100
    k = i + j
    l = k * a

    return {
        "mrp_excl_tax":  round(f, 4),
        "retail_price":  round(g, 4),
        "sales_price":   round(i, 4),
        "tax_amount":    round(j, 4),
        "gross_rate":    round(k, 4),
        "net_rate":      round(l, 4),
    }


# ─────────────────────────────────────────────────────────────
# DOCUMENT CRUD
# ─────────────────────────────────────────────────────────────

def pob_create_document(doc_type, doc_date, party_type, party_id,
                        party_name, user_id) -> str:
    """Create header row. Returns new document id or None."""
    doc_no = pob_generate_doc_no(doc_type)
    rows = _exec(
        admin_supabase.table("pob_documents").insert({
            "doc_no":     doc_no,
            "doc_type":   doc_type,
            "doc_date":   str(doc_date),
            "party_type": party_type,
            "party_id":   str(party_id),
            "party_name": party_name,
            "status":     "pending",
            "user_id":    str(user_id),
            "created_by": str(user_id),
        }),
        "Error creating document"
    )
    return rows[0]["id"] if rows else None


def pob_load_document(doc_id) -> dict:
    try:
        resp = admin_supabase.table("pob_documents") \
            .select("*") \
            .eq("id", str(doc_id)) \
            .single() \
            .execute()
        return resp.data
    except:
        return None


def pob_submit_document(doc_id) -> bool:
    rows = _exec(
        admin_supabase.table("pob_documents").update({
            "submitted_at": datetime.now().isoformat(),
            "updated_at":   datetime.now().isoformat(),
        }).eq("id", str(doc_id)),
        "Error submitting document"
    )
    return True


# ─────────────────────────────────────────────────────────────
# LINE CRUD
# ─────────────────────────────────────────────────────────────

def pob_save_line(pob_doc_id, product_id, product_name, seq_no,
                  sale_qty, free_qty, mrp_incl_tax, tax_rate, discount,
                  mrp_excl_tax, retail_price, sales_price,
                  tax_amount, gross_rate, net_rate) -> bool:
    rows = _exec(
        admin_supabase.table("pob_lines").insert({
            "pob_document_id": str(pob_doc_id),
            "product_id":      str(product_id),
            "product_name":    product_name,
            "sequence_no":     int(seq_no),
            "sale_qty":        float(sale_qty),
            "free_qty":        float(free_qty),
            "mrp_incl_tax":    float(mrp_incl_tax),
            "tax_rate":        float(tax_rate),
            "discount":        float(discount),
            "mrp_excl_tax":    float(mrp_excl_tax),
            "retail_price":    float(retail_price),
            "sales_price":     float(sales_price),
            "tax_amount":      float(tax_amount),
            "gross_rate":      float(gross_rate),
            "net_rate":        float(net_rate),
        }),
        "Error saving line"
    )
    return len(rows) > 0


def pob_update_line(line_id, sale_qty, free_qty, mrp_incl_tax, tax_rate,
                    discount, mrp_excl_tax, retail_price, sales_price,
                    tax_amount, gross_rate, net_rate) -> bool:
    _exec(
        admin_supabase.table("pob_lines").update({
            "sale_qty":     float(sale_qty),
            "free_qty":     float(free_qty),
            "mrp_incl_tax": float(mrp_incl_tax),
            "tax_rate":     float(tax_rate),
            "discount":     float(discount),
            "mrp_excl_tax": float(mrp_excl_tax),
            "retail_price": float(retail_price),
            "sales_price":  float(sales_price),
            "tax_amount":   float(tax_amount),
            "gross_rate":   float(gross_rate),
            "net_rate":     float(net_rate),
            "updated_at":   datetime.now().isoformat(),
        }).eq("id", str(line_id)),
        "Error updating line"
    )
    return True


def pob_delete_line(line_id) -> bool:
    _exec(
        admin_supabase.table("pob_lines").delete().eq("id", str(line_id)),
        "Error deleting line"
    )
    return True


def pob_load_lines(pob_doc_id) -> list:
    return _exec(
        admin_supabase.table("pob_lines")
        .select("*")
        .eq("pob_document_id", str(pob_doc_id))
        .order("sequence_no"),
        "Error loading lines"
    )


# ─────────────────────────────────────────────────────────────
# ARCHIVE
# ─────────────────────────────────────────────────────────────

def pob_load_archive(user_id, role, status_filter="ALL",
                     doc_type_filter="ALL") -> list:
    """Admin sees all; user sees only their own."""
    q = admin_supabase.table("pob_documents") \
        .select("*, users!pob_documents_user_fkey(username)") \
        .eq("is_deleted", False) \
        .order("created_at", desc=True)

    if role != "admin":
        q = q.eq("user_id", str(user_id))
    if status_filter and status_filter != "ALL":
        q = q.eq("status", status_filter.lower())
    if doc_type_filter and doc_type_filter != "ALL":
        q = q.eq("doc_type", doc_type_filter)

    return _exec(q, "Error loading archive")


# ─────────────────────────────────────────────────────────────
# ADMIN APPROVAL
# ─────────────────────────────────────────────────────────────

def pob_approve(doc_id, admin_user_id, comment="") -> bool:
    _exec(
        admin_supabase.table("pob_documents").update({
            "status":           "approved",
            "approved_by":      str(admin_user_id),
            "approved_at":      datetime.now().isoformat(),
            "approval_comment": comment,
            "updated_at":       datetime.now().isoformat(),
        }).eq("id", str(doc_id)),
        "Error approving"
    )
    return True


def pob_reject(doc_id, admin_user_id, comment="") -> bool:
    _exec(
        admin_supabase.table("pob_documents").update({
            "status":           "rejected",
            "approved_by":      str(admin_user_id),
            "approved_at":      datetime.now().isoformat(),
            "approval_comment": comment,
            "updated_at":       datetime.now().isoformat(),
        }).eq("id", str(doc_id)),
        "Error rejecting"
    )
    return True


# ─────────────────────────────────────────────────────────────
# EXPORT HELPERS
# ─────────────────────────────────────────────────────────────

def pob_format_whatsapp(doc: dict, lines: list) -> str:
    labels = {"POB": "POB", "STATEMENT": "Statement", "CR_NT": "Credit Note"}
    label  = labels.get(doc["doc_type"], doc["doc_type"])
    body   = ""
    total  = 0.0
    for i, ln in enumerate(lines, 1):
        body  += (f"\n{i}. {ln['product_name']}\n"
                  f"   Qty: {ln['sale_qty']} + {ln['free_qty']} free\n"
                  f"   Net: ₹{float(ln['net_rate']):.2f}\n")
        total += float(ln["net_rate"])
    return (f"*{label} — {doc['doc_no']}*\n"
            f"Date: {doc['doc_date']}\n"
            f"Party: {doc['party_name']}\n"
            f"{'─'*28}"
            f"{body}"
            f"{'─'*28}\n"
            f"*Total: ₹{total:.2f}*")


def pob_generate_pdf(doc: dict, lines: list) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Table,
                                        TableStyle, Paragraph, Spacer)
        from reportlab.lib.styles import getSampleStyleSheet
        import io

        buf    = io.BytesIO()
        pdf    = SimpleDocTemplate(buf, pagesize=A4,
                                   leftMargin=15*mm, rightMargin=15*mm,
                                   topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        green  = colors.HexColor("#1a6b5a")
        story  = []

        labels = {"POB": "PROOF OF BUSINESS", "STATEMENT": "STATEMENT",
                  "CR_NT": "CREDIT NOTE"}
        story.append(Paragraph(f"<b>{labels.get(doc['doc_type'], doc['doc_type'])}</b>",
                                styles["Title"]))
        story.append(Spacer(1, 4*mm))

        hdr = [
            ["Doc No:", doc["doc_no"],    "Date:",   str(doc["doc_date"])],
            ["Party:",  doc["party_name"], "Type:",  doc["party_type"].capitalize()],
            ["Status:", doc["status"].upper(), "", ""],
        ]
        ht = Table(hdr, colWidths=[28*mm, 72*mm, 22*mm, 55*mm])
        ht.setStyle(TableStyle([
            ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
            ("FONTNAME",      (2,0),(2,-1), "Helvetica-Bold"),
            ("FONTNAME",      (1,0),(-1,-1),"Helvetica"),
            ("FONTSIZE",      (0,0),(-1,-1), 9),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ]))
        story.append(ht)
        story.append(Spacer(1, 6*mm))

        cols = ["#","Product","SaleQty","FreeQty",
                "MRP\n(Incl)","Tax%","Disc%",
                "Sales\nPrice","Tax\nAmt","Gross\nRate","Net Rate"]
        data  = [cols]
        total = 0.0
        for idx, ln in enumerate(lines, 1):
            data.append([
                str(idx), ln["product_name"],
                str(ln["sale_qty"]), str(ln["free_qty"]),
                f"₹{float(ln['mrp_incl_tax']):.2f}",
                f"{ln['tax_rate']}%", f"{ln['discount']}%",
                f"₹{float(ln['sales_price']):.2f}",
                f"₹{float(ln['tax_amount']):.2f}",
                f"₹{float(ln['gross_rate']):.2f}",
                f"₹{float(ln['net_rate']):.2f}",
            ])
            total += float(ln["net_rate"])
        data.append(["","TOTAL","","","","","","","","",f"₹{total:.2f}"])

        cw  = [8*mm,40*mm,12*mm,12*mm,18*mm,10*mm,10*mm,18*mm,14*mm,16*mm,18*mm]
        pt  = Table(data, colWidths=cw, repeatRows=1)
        pt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  green),
            ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
            ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",      (0,0), (-1,-1), 7),
            ("ALIGN",         (2,0), (-1,-1), "RIGHT"),
            ("ROWBACKGROUNDS",(0,1), (-1,-2), [colors.white,
                                               colors.HexColor("#f0f8f5")]),
            ("BACKGROUND",    (0,-1),(-1,-1), colors.HexColor("#d8ede8")),
            ("FONTNAME",      (0,-1),(-1,-1), "Helvetica-Bold"),
            ("GRID",          (0,0), (-1,-1), 0.3, colors.grey),
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]))
        story.append(pt)
        pdf.build(story)
        return buf.getvalue()

    except ImportError:
        return None
    except Exception as e:
        st.error(f"PDF error: {e}")
        return None
