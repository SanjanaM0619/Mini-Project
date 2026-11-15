from typing import Any

import streamlit as st


def apply_custom_theme():
    """Inject production FAANG-grade CSS with smooth micro-interactions and tactile feedback."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            /* Global styling & high-contrast typography */
            html, body, [class*="css"], .stApp {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                background-color: #F8FAFC !important;
                color: #0F172A !important;
                -webkit-font-smoothing: antialiased;
            }

            /* Container layout & generous whitespace */
            .block-container {
                padding-top: 2rem;
                padding-bottom: 3.5rem;
                padding-left: 3rem;
                padding-right: 3rem;
                max-width: 1240px;
            }

            /* Sidebar: Clean minimal border, pure white surface */
            [data-testid="stSidebar"] {
                background-color: #FFFFFF !important;
                border-right: 1px solid #E2E8F0 !important;
            }

            /* Production Metric Cards */
            .kpi-card {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 18px 22px;
                box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
                transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.18s cubic-bezier(0.16, 1, 0.3, 1);
            }
            .kpi-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 16px -2px rgba(15, 23, 42, 0.08);
            }
            .kpi-title {
                font-size: 0.78rem;
                font-weight: 600;
                color: #64748B;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                margin-bottom: 6px;
            }
            .kpi-value {
                font-size: 1.85rem;
                font-weight: 700;
                color: #0F172A;
                line-height: 1.15;
                letter-spacing: -0.02em;
            }
            .kpi-subtitle {
                font-size: 0.8rem;
                color: #94A3B8;
                margin-top: 6px;
                font-weight: 500;
            }

            /* Subtle Status Badges */
            .badge-safe {
                background-color: #F0FDF4;
                color: #166534;
                border: 1px solid #BBF7D0;
                padding: 3px 9px;
                border-radius: 6px;
                font-size: 0.75rem;
                font-weight: 600;
                letter-spacing: 0.02em;
            }
            .badge-at-risk {
                background-color: #FFFBEB;
                color: #92400E;
                border: 1px solid #FDE68A;
                padding: 3px 9px;
                border-radius: 6px;
                font-size: 0.75rem;
                font-weight: 600;
                letter-spacing: 0.02em;
            }
            .badge-critical {
                background-color: #FEF2F2;
                color: #991B1B;
                border: 1px solid #FECACA;
                padding: 3px 9px;
                border-radius: 6px;
                font-size: 0.75rem;
                font-weight: 600;
                letter-spacing: 0.02em;
            }
            .badge-expired {
                background-color: #F8FAFC;
                color: #64748B;
                border: 1px solid #E2E8F0;
                padding: 3px 9px;
                border-radius: 6px;
                font-size: 0.75rem;
                font-weight: 600;
            }

            /* Input Fields: Crisp borders & focus glow */
            .stTextInput input {
                border-radius: 6px !important;
                border: 1px solid #CBD5E1 !important;
                background-color: #FFFFFF !important;
                color: #0F172A !important;
                font-size: 0.9rem !important;
                padding: 10px 14px !important;
                transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
            }
            .stTextInput input:focus {
                border-color: #2563EB !important;
                box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
                outline: none !important;
            }

            /* Buttons: Tactile feel with active click compression */
            .stButton > button {
                background-color: #0F172A !important;
                color: #FFFFFF !important;
                border: 1px solid #0F172A !important;
                border-radius: 6px !important;
                font-weight: 500 !important;
                font-size: 0.88rem !important;
                padding: 8px 18px !important;
                box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
                transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1) !important;
                cursor: pointer !important;
            }
            .stButton > button:hover {
                background-color: #1E293B !important;
                border-color: #1E293B !important;
                transform: translateY(-1px) !important;
                box-shadow: 0 3px 8px -1px rgba(15, 23, 42, 0.15) !important;
            }
            .stButton > button:active {
                transform: scale(0.985) !important;
                box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
            }

            /* Tabs: Minimal underline border style */
            .stTabs [data-baseweb="tab-list"] {
                gap: 16px;
                border-bottom: 1px solid #E2E8F0;
                background-color: transparent !important;
            }
            .stTabs [data-baseweb="tab"] {
                padding: 10px 4px;
                font-weight: 500;
                font-size: 0.9rem;
                color: #64748B;
                border: none !important;
                background: transparent !important;
                transition: color 0.15s ease;
            }
            .stTabs [data-baseweb="tab"]:hover {
                color: #0F172A;
            }
            .stTabs [aria-selected="true"] {
                color: #0F172A !important;
                font-weight: 600 !important;
                border-bottom: 2px solid #0F172A !important;
            }

            /* Clean containers */
            [data-testid="stVerticalBlock"] > div[data-testid="stForm"],
            div[data-testid="stExpander"],
            div[data-testid="stContainer"] {
                border-radius: 8px !important;
                border: 1px solid #E2E8F0 !important;
                background-color: #FFFFFF !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(title: str, value: Any, subtitle: str = ""):
    """Render a clean FAANG-grade white KPI metric card."""
    sub_html = f'<div class="kpi-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )