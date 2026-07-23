"""
Let's Go — GPS Tracking Report (Admin Only)
Place at: modules/lets_go/lets_go_report.py

Reads server-side tables written by the Flutter app:
  tracking_sessions, tracking_pings, tracking_stops,
  tracking_events, session_routes (archives)

Features:
  Tab 1 — Daily Overview: all reps for a date range (sessions, KM, stops)
  Tab 2 — Session Detail: route map, stops with matched doctors, events
Timestamps are stored in UTC; displayed here in IST (+5:30).
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from anchors.supabase_client import admin_supabase, safe_exec

IST_OFFSET = timedelta(hours=5, minutes=30)
MAX_PINGS = 15000          # safety cap per session
CHUNK = 1000               # supabase page size


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _to_ist(ts_str, fmt="%H:%M"):
    """Convert UTC ISO timestamp string to IST display string."""
    if not ts_str:
        return "—"
    try:
        s = str(ts_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return (dt + IST_OFFSET).strftime(fmt)
    except Exception:
        return str(ts_str)[:16]


def _get_users():
    """id → username map for all users."""
    rows = safe_exec(
        admin_supabase.table("users")
        .select("id, username, designation, is_active")
        .order("username"),
        "Error loading users"
    )
    return rows or []


def _get_sessions(from_d, to_d, user_id=None):
    q = (admin_supabase.table("tracking_sessions")
         .select("*")
         .gte("session_date", from_d.isoformat())
         .lte("session_date", to_d.isoformat())
         .order("session_date", desc=True)
         .order("start_time", desc=True))
    if user_id:
        q = q.eq("user_id", user_id)
    return safe_exec(q, "Error loading sessions") or []


def _get_pings(session_id):
    """Fetch ALL pings for a session in pages of 1000 (avoids the row cap)."""
    all_rows = []
    start = 0
    while start < MAX_PINGS:
        rows = safe_exec(
            admin_supabase.table("tracking_pings")
            .select("latitude, longitude, snapped_latitude, snapped_longitude, "
                    "ping_time, speed, battery_level, gps_status, internet_status, "
                    "segment_km, is_moving")
            .eq("session_id", session_id)
            .order("ping_time")
            .range(start, start + CHUNK - 1),
            "Error loading GPS pings"
        ) or []
        all_rows.extend(rows)
        if len(rows) < CHUNK:
            break
        start += CHUNK
    return all_rows


def _get_archived_route(session_id):
    """Fallback for sessions archived by the monthly pg_cron job."""
    rows = safe_exec(
        admin_supabase.table("session_routes")
        .select("route_points, total_km")
        .eq("session_id", session_id)
        .limit(1),
        "Error loading archived route"
    ) or []
    if not rows:
        return []
    pts = rows[0].get("route_points") or []
    if isinstance(pts, dict):
        pts = pts.get("points", [])
    out = []
    for p in pts:
        if not isinstance(p, dict):
            continue
        lat = p.get("latitude", p.get("lat"))
        lng = p.get("longitude", p.get("lng", p.get("lon")))
        if lat is not None and lng is not None:
            out.append({"latitude": lat, "longitude": lng,
                        "snapped_latitude": None, "snapped_longitude": None,
                        "ping_time": p.get("ping_time", p.get("t", ""))})
    return out


def _get_stops(session_id):
    return safe_exec(
        admin_supabase.table("tracking_stops")
        .select("*")
        .eq("session_id", session_id)
        .order("arrived_at"),
        "Error loading stops"
    ) or []


def _get_events(session_id):
    return safe_exec(
        admin_supabase.table("tracking_events")
        .select("event_type, event_time, battery_level, details")
        .eq("session_id", session_id)
        .order("event_time"),
        "Error loading events"
    ) or []


def _fmt_names(val):
    """Array/list column → comma string."""
    if not val:
        return ""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val if v)
    return str(val)


def _duration_str(start_ts, end_ts):
    try:
        s = datetime.fromisoformat(str(start_ts).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(end_ts).replace("Z", "+00:00"))
        mins = int((e - s).total_seconds() // 60)
        return f"{mins // 60}h {mins % 60}m"
    except Exception:
        return "—"


# ──────────────────────────────────────────────────────────────
# Tab 1 — Daily Overview
# ──────────────────────────────────────────────────────────────

def _tab_overview(users):
    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        from_d = st.date_input("From", value=date.today(), key="lg_ov_from")
    with col2:
        to_d = st.date_input("To", value=date.today(), key="lg_ov_to")
    with col3:
        user_opts = {"ALL": "All Representatives"}
        user_opts.update({u["id"]: u["username"] for u in users})
        sel_user = st.selectbox("Representative", list(user_opts.keys()),
                                format_func=lambda x: user_opts[x], key="lg_ov_user")

    if from_d > to_d:
        st.warning("'From' date is after 'To' date.")
        return

    sessions = _get_sessions(from_d, to_d,
                             None if sel_user == "ALL" else sel_user)
    if not sessions:
        st.info("No tracking sessions found for this selection.")
        return

    uname = {u["id"]: u["username"] for u in users}

    # ── Summary metrics ──────────────────────────────────────
    total_km = sum(float(s.get("total_km") or 0) for s in sessions)
    total_stops = sum(int(s.get("total_stops") or 0) for s in sessions)
    active_now = sum(1 for s in sessions if s.get("status") == "active")
    reps_worked = len({s["user_id"] for s in sessions})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sessions", len(sessions))
    m2.metric("Reps Worked", reps_worked)
    m3.metric("Total KM", f"{total_km:,.1f}")
    m4.metric("Total Stops", total_stops)
    if active_now:
        st.success(f"🟢 {active_now} session(s) currently ACTIVE")

    # ── Table ────────────────────────────────────────────────
    rows = []
    for s in sessions:
        rows.append({
            "Date": s.get("session_date", ""),
            "Rep": uname.get(s.get("user_id"), "Unknown"),
            "Start (IST)": _to_ist(s.get("start_time")),
            "End (IST)": _to_ist(s.get("end_time")) if s.get("end_time") else "🟢 active",
            "Duration": _duration_str(s.get("start_time"), s.get("end_time"))
                        if s.get("end_time") else "—",
            "KM": round(float(s.get("total_km") or 0), 1),
            "Stops": int(s.get("total_stops") or 0),
            "GPS Off": int(s.get("gps_off_count") or 0),
            "Net Off": int(s.get("internet_off_count") or 0),
            "Battery": f"{s.get('start_battery') or '—'}% → {s.get('end_battery') or '—'}%",
            "Status": s.get("status", ""),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Per-rep totals (useful for expenses later) ───────────
    with st.expander("📊 Totals per Representative"):
        agg = {}
        for s in sessions:
            k = uname.get(s.get("user_id"), "Unknown")
            a = agg.setdefault(k, {"Sessions": 0, "KM": 0.0, "Stops": 0})
            a["Sessions"] += 1
            a["KM"] += float(s.get("total_km") or 0)
            a["Stops"] += int(s.get("total_stops") or 0)
        adf = pd.DataFrame(
            [{"Rep": k, "Sessions": v["Sessions"],
              "Total KM": round(v["KM"], 1), "Total Stops": v["Stops"]}
             for k, v in sorted(agg.items())]
        )
        st.dataframe(adf, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# Tab 2 — Session Detail (map, stops, events)
# ──────────────────────────────────────────────────────────────

def _tab_detail(users):
    col1, col2 = st.columns([2, 3])
    with col1:
        pick_d = st.date_input("Session date", value=date.today(), key="lg_dt_date")
    with col2:
        user_opts = {u["id"]: u["username"] for u in users}
        sel_user = st.selectbox("Representative", list(user_opts.keys()),
                                format_func=lambda x: user_opts[x], key="lg_dt_user")

    sessions = _get_sessions(pick_d, pick_d, sel_user)
    if not sessions:
        st.info("No sessions for this rep on this date.")
        return

    sess_label = {
        s["id"]: f"{_to_ist(s.get('start_time'))} → "
                 f"{_to_ist(s.get('end_time')) if s.get('end_time') else 'active'} "
                 f"({float(s.get('total_km') or 0):.1f} km, {s.get('status','')})"
        for s in sessions
    }
    sel_sess = st.selectbox("Session", list(sess_label.keys()),
                            format_func=lambda x: sess_label[x], key="lg_dt_sess")
    sess = next(s for s in sessions if s["id"] == sel_sess)

    # ── Session summary ──────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Start (IST)", _to_ist(sess.get("start_time")))
    m2.metric("End (IST)", _to_ist(sess.get("end_time")) if sess.get("end_time") else "Active")
    m3.metric("Total KM", f"{float(sess.get('total_km') or 0):.1f}")
    m4.metric("Stops", int(sess.get("total_stops") or 0))
    m5.metric("Battery", f"{sess.get('start_battery') or '—'}→{sess.get('end_battery') or '—'}%")

    # ── Route data (live tables, else archive) ───────────────
    with st.spinner("Loading route..."):
        pings = _get_pings(sel_sess)
        from_archive = False
        if not pings:
            pings = _get_archived_route(sel_sess)
            from_archive = bool(pings)

    stops = _get_stops(sel_sess)

    if not pings and not stops:
        st.warning("No GPS data found for this session (it may not have synced yet).")
        return
    if from_archive:
        st.caption("📦 Route loaded from monthly archive (session older than 60 days).")
    elif pings:
        st.caption(f"🛰️ {len(pings):,} GPS points loaded.")

    # ── Map ──────────────────────────────────────────────────
    path = []
    for p in pings:
        lat = p.get("snapped_latitude") or p.get("latitude")
        lng = p.get("snapped_longitude") or p.get("longitude")
        if lat is not None and lng is not None:
            path.append([float(lng), float(lat)])

    try:
        import pydeck as pdk
        layers = []

        if path:
            layers.append(pdk.Layer(
                "PathLayer",
                data=[{"path": path}],
                get_path="path",
                get_color=[26, 107, 90],
                width_min_pixels=4,
            ))
            layers.append(pdk.Layer(  # start marker (green)
                "ScatterplotLayer",
                data=[{"pos": path[0]}],
                get_position="pos",
                get_fill_color=[46, 155, 100],
                get_radius=60, radius_min_pixels=8,
            ))
            layers.append(pdk.Layer(  # end marker (dark)
                "ScatterplotLayer",
                data=[{"pos": path[-1]}],
                get_position="pos",
                get_fill_color=[30, 30, 30],
                get_radius=60, radius_min_pixels=8,
            ))

        stop_data = []
        for i, sp in enumerate(stops, 1):
            if sp.get("latitude") is None:
                continue
            stop_data.append({
                "pos": [float(sp["longitude"]), float(sp["latitude"])],
                "label": (f"Stop {i}: {_to_ist(sp.get('arrived_at'))}"
                          f" ({sp.get('duration_minutes') or '?'} min)"
                          + (f" — {_fmt_names(sp.get('matched_doctor_names'))}"
                             if sp.get("matched_doctor_names") else "")),
            })
        if stop_data:
            layers.append(pdk.Layer(
                "ScatterplotLayer",
                data=stop_data,
                get_position="pos",
                get_fill_color=[192, 57, 43],
                get_radius=50, radius_min_pixels=7,
                pickable=True,
            ))

        if path:
            center = path[len(path) // 2]
        elif stop_data:
            center = stop_data[0]["pos"]
        else:
            center = [88.36, 22.57]

        st.pydeck_chart(pdk.Deck(
            map_style=None,
            initial_view_state=pdk.ViewState(
                longitude=center[0], latitude=center[1], zoom=12),
            layers=layers,
            tooltip={"text": "{label}"},
        ))
        st.caption("🟢 Start · ⚫ End · 🔴 Stops (hover a stop for details) · Green line = route")
    except Exception as e:
        st.error(f"Map could not be drawn: {e}")
        if path:
            st.map(pd.DataFrame(
                [{"lat": p[1], "lon": p[0]} for p in path[::10]]))

    # ── Stops table ──────────────────────────────────────────
    st.markdown("#### 🛑 Stops")
    if stops:
        srows = []
        for i, sp in enumerate(stops, 1):
            srows.append({
                "#": i,
                "Arrived (IST)": _to_ist(sp.get("arrived_at")),
                "Departed (IST)": _to_ist(sp.get("departed_at")) if sp.get("departed_at") else "—",
                "Minutes": sp.get("duration_minutes") or "—",
                "Type": sp.get("stop_type", ""),
                "Matched Doctors": _fmt_names(sp.get("matched_doctor_names")) or "—",
                "Note": sp.get("admin_note") or "",
            })
        st.dataframe(pd.DataFrame(srows), use_container_width=True, hide_index=True)
    else:
        st.info("No stops recorded in this session.")

    # ── Events timeline ──────────────────────────────────────
    with st.expander("⚡ Session Events (GPS/network/battery)"):
        events = _get_events(sel_sess)
        if events:
            erows = [{
                "Time (IST)": _to_ist(e.get("event_time"), "%H:%M:%S"),
                "Event": e.get("event_type", ""),
                "Battery": f"{e.get('battery_level')}%" if e.get("battery_level") is not None else "—",
                "Details": e.get("details") or "",
            } for e in events]
            st.dataframe(pd.DataFrame(erows), use_container_width=True, hide_index=True)
        else:
            st.info("No events recorded.")


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def run_lets_go_report():
    role = st.session_state.get("role", "user")
    if role != "admin":
        st.warning("⚠️ This report is available to admin only.")
        return

    st.title("🛰️ Let's Go — Field Tracking Report")
    st.caption("GPS sessions from the field app · times shown in IST")

    users = _get_users()
    if not users:
        st.error("Could not load users.")
        return

    tab1, tab2 = st.tabs(["📅 Daily Overview", "🗺️ Session Detail"])
    with tab1:
        _tab_overview(users)
    with tab2:
        _tab_detail(users)

