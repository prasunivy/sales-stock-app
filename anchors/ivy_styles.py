"""
Ivy Pharmaceuticals — UI Styling
Apply this in app.py via: apply_styles()
Clean & Professional theme — optimised for mobile + desktop

MOBILE STRATEGY:
- On mobile: fixed bottom navigation bar with key modules
- On desktop: normal left sidebar
"""

IVY_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

:root {
    --ivy-green:        #1a6b5a;
    --ivy-green-light:  #e8f5f1;
    --ivy-green-mid:    #2d9b7f;
    --ivy-accent:       #f0faf7;
    --ivy-white:        #ffffff;
    --ivy-bg:           #f7f9f8;
    --ivy-border:       #e2ece9;
    --ivy-text:         #1c2b27;
    --ivy-text-soft:    #5a7268;
    --ivy-text-muted:   #9ab4ad;
    --ivy-danger:       #c0392b;
    --ivy-warning:      #e67e22;
    --ivy-shadow:       0 2px 12px rgba(26,107,90,0.08);
    --ivy-radius:       12px;
    --ivy-radius-sm:    8px;
    --ivy-font:         'DM Sans', sans-serif;
    --ivy-mono:         'DM Mono', monospace;
}

html, body, [class*="css"] {
    font-family: var(--ivy-font) !important;
    color: var(--ivy-text) !important;
}

.stApp { background-color: var(--ivy-bg) !important; }

/* ── SIDEBAR ─────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--ivy-white) !important;
    border-right: 1px solid var(--ivy-border) !important;
    box-shadow: 2px 0 16px rgba(26,107,90,0.06) !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: var(--ivy-text-muted) !important;
    margin-top: 1rem !important;
    margin-bottom: 0.3rem !important;
}

[data-testid="stSidebar"] .stButton > button {
    width: 100% !important;
    text-align: left !important;
    background: transparent !important;
    border: none !important;
    border-radius: var(--ivy-radius-sm) !important;
    color: var(--ivy-text) !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 0.8rem !important;
    margin-bottom: 2px !important;
    box-shadow: none !important;
    transition: all 0.15s ease !important;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--ivy-green-light) !important;
    color: var(--ivy-green) !important;
    font-weight: 500 !important;
}

[data-testid="stSidebar"] hr {
    border-color: var(--ivy-border) !important;
    margin: 0.6rem 0 !important;
}

/* ── MAIN CONTENT ────────────────────────────── */
.main .block-container {
    padding: 2rem 2rem 4rem 2rem !important;
    max-width: 1100px !important;
}

/* ── HEADINGS ────────────────────────────────── */
h1 { font-size: 1.6rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; }

/* ── BUTTONS ─────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: var(--ivy-green) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.4rem !important;
    box-shadow: 0 2px 8px rgba(26,107,90,0.25) !important;
}

.stButton > button[kind="primary"]:hover {
    background: var(--ivy-green-mid) !important;
    transform: translateY(-1px) !important;
}

.stButton > button {
    background: var(--ivy-white) !important;
    color: var(--ivy-text) !important;
    border: 1.5px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.15s ease !important;
}

.stButton > button:hover {
    border-color: var(--ivy-green) !important;
    color: var(--ivy-green) !important;
}

/* ── INPUTS ──────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    border: 1.5px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius-sm) !important;
    background: var(--ivy-white) !important;
    font-family: var(--ivy-font) !important;
    font-size: 0.92rem !important;
}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--ivy-green) !important;
    box-shadow: 0 0 0 3px rgba(26,107,90,0.1) !important;
}

.stTextInput label, .stNumberInput label, .stTextArea label,
.stSelectbox label, .stMultiSelect label, .stRadio label,
.stCheckbox label, .stDateInput label {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    color: var(--ivy-text-soft) !important;
}

/* ── TABLES ──────────────────────────────────── */
.stDataFrame {
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius) !important;
    overflow: hidden !important;
    box-shadow: var(--ivy-shadow) !important;
}

.stDataFrame thead th {
    background: var(--ivy-green) !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    padding: 0.65rem 1rem !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 2 !important;
}

.stDataFrame tbody tr:nth-child(even) { background: var(--ivy-accent) !important; }
.stDataFrame tbody tr:hover { background: var(--ivy-green-light) !important; }
.stDataFrame tbody td {
    padding: 0.5rem 1rem !important;
    border-bottom: 1px solid var(--ivy-border) !important;
    font-size: 0.83rem !important;
}

/* ── METRICS ─────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--ivy-white) !important;
    border: 1px solid var(--ivy-border) !important;
    border-radius: var(--ivy-radius) !important;
    padding: 1rem 1.2rem !important;
    box-shadow: var(--ivy-shadow) !important;
}

[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    color: var(--ivy-text-soft) !important;
}

[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: var(--ivy-green) !important;
}

/* ── TABS ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--ivy-white) !important;
    border-bottom: 2px solid var(--ivy-border) !important;
}

.stTabs [data-baseweb="tab"] {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: var(--ivy-text-soft) !important;
    padding: 0.65rem 1.1rem !important;
}

.stTabs [aria-selected="true"] {
    color: var(--ivy-green) !important;
    border-bottom: 2px solid var(--ivy-green) !important;
    font-weight: 600 !important;
    background: var(--ivy-green-light) !important;
}

/* ── SCROLLBAR ───────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--ivy-bg); }
::-webkit-scrollbar-thumb { background: var(--ivy-border); border-radius: 3px; }

/* ── HIDE STREAMLIT BRANDING ─────────────────── */
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
[data-testid="stToolbar"] { display: none !important; }

/* ── DIVIDERS ────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--ivy-border) !important;
    margin: 1.2rem 0 !important;
}

/* ── MOBILE ──────────────────────────────────── */
@media (max-width: 768px) {
    .main .block-container {
        padding: 0.8rem 0.7rem 6rem 0.7rem !important;
    }
    h1 { font-size: 1.2rem !important; }
    h2 { font-size: 1rem !important; }
    h3 { font-size: 0.9rem !important; }

    .stButton > button {
        width: 100% !important;
        min-height: 48px !important;
        font-size: 0.95rem !important;
    }

    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        font-size: 1rem !important;
        min-height: 48px !important;
    }

    .stDataFrame { overflow-x: auto !important; }
    .stDataFrame table { font-size: 0.72rem !important; }
    .stDataFrame tbody td,
    .stDataFrame thead th { padding: 0.4rem 0.5rem !important; }

    /* Hide sidebar on mobile — we use bottom nav instead */
    [data-testid="stSidebar"] {
        display: none !important;
    }

    [data-testid="collapsedControl"] {
        display: none !important;
    }
}

/* ── MOBILE BOTTOM NAV BAR ───────────────────── */
#ivy-mobile-nav {
    display: none;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    background: var(--ivy-white);
    border-top: 1px solid var(--ivy-border);
    box-shadow: 0 -4px 20px rgba(26,107,90,0.12);
    padding: 0;
    height: 60px;
    overflow-x: auto;
    overflow-y: hidden;
    white-space: nowrap;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
}

#ivy-mobile-nav::-webkit-scrollbar { display: none; }

#ivy-mobile-nav a {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 72px;
    height: 60px;
    padding: 6px 8px;
    text-decoration: none;
    color: var(--ivy-text-soft);
    font-size: 0.6rem;
    font-weight: 500;
    font-family: var(--ivy-font);
    border-right: 1px solid var(--ivy-border);
    transition: background 0.15s;
    -webkit-tap-highlight-color: transparent;
}

#ivy-mobile-nav a:last-child { border-right: none; }

#ivy-mobile-nav a .nav-icon {
    font-size: 1.3rem;
    margin-bottom: 2px;
    line-height: 1;
}

#ivy-mobile-nav a:active,
#ivy-mobile-nav a.active {
    background: var(--ivy-green-light);
    color: var(--ivy-green);
}

@media (max-width: 768px) {
    #ivy-mobile-nav { display: flex; }
}

</style>
"""

MOBILE_NAV_HTML = """
<div id="ivy-mobile-nav">
  <a href="?nav=STATEMENT" onclick="setModule('STATEMENT')">
    <span class="nav-icon">📦</span>Statement
  </a>
  <a href="?nav=OPS" onclick="setModule('OPS')">
    <span class="nav-icon">📥</span>OPS
  </a>
  <a href="?nav=DCR" onclick="setModule('DCR')">
    <span class="nav-icon">📞</span>DCR
  </a>
  <a href="?nav=DOCTOR_FETCH" onclick="setModule('DOCTOR_FETCH')">
    <span class="nav-icon">🔍</span>Doctor
  </a>
  <a href="?nav=DOCTOR_IO" onclick="setModule('DOCTOR_IO')">
    <span class="nav-icon">📊</span>Doc I/O
  </a>
  <a href="?nav=TOUR" onclick="setModule('TOUR')">
    <span class="nav-icon">🗓️</span>Tour
  </a>
  <a href="?nav=POB" onclick="setModule('POB')">
    <span class="nav-icon">📋</span>POB
  </a>
  <a href="?nav=REPORTS" onclick="setModule('REPORTS')">
    <span class="nav-icon">📈</span>Reports
  </a>
</div>
"""


def apply_styles():
    """Apply all Ivy Pharmaceuticals styles + mobile nav."""
    import streamlit as st
    st.markdown(IVY_CSS, unsafe_allow_html=True)
    # Show mobile bottom nav only when logged in
    if st.session_state.get("auth_user"):
        st.markdown(MOBILE_NAV_HTML, unsafe_allow_html=True)
