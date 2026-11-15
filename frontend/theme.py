from typing import Any

import streamlit as st


def apply_custom_theme():
    """Inject corporate, clean, non-overlapping light theme CSS."""
    st.markdown(
        """
        <style>
            /* Main background & font smoothing */
            .stApp {
                background-color: #F8FAFC;
                color: #0F172A;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }

            /* Clean top header spacing */
            .block-container {
                padding-top: 2rem;
                padding-bottom: 3rem;
                padding-left: 2.5rem;
                padding-right: 2.5rem;
                max-width: 1280px;
            }

            /* Sidebar styling */
            [data-testid="stSidebar"] {
                background-color: #FFFFFF !important;
                border-right: 1px solid #E2E8F0;
            }

            /* Metric Card styling */
            .kpi-card {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
                padding: 16px 20px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
                margin-bottom: 12px;
            }
            .kpi-title {
                font-size: 0.85rem;
                font-weight: 600;
                color: #64748B;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 4px;
            }
            .kpi-value {
                font-size: 1.8rem;
                font-weight: 700;
                color: #1E3A8A;
                line-height: 1.2;
            }
            .kpi-subtitle {
                font-size: 0.8rem;
                color: #94A3B8;
                margin-top: 4px;
            }

            /* Clean Badge Tags */
            .badge-safe {
                background-color: #DCFCE7;
                color: #15803D;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: 600;
            }
            .badge-at-risk {
                background-color: #FEF3C7;
                color: #B45309;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: 600;
            }
            .badge-critical {
                background-color: #FEE2E2;
                color: #B91C1C;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: 600;
            }
            .badge-expired {
                background-color: #F1F5F9;
                color: #64748B;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.8rem;
                font-weight: 600;
                text-decoration: line-through;
            }

            /* Primary button styling */
            .stButton > button {
                background-color: #1E3A8A;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                padding: 0.5rem 1.2rem;
                transition: background-color 0.2s ease;
            }
            .stButton > button:hover {
                background-color: #1E40AF;
                color: #FFFFFF;
            }

            /* Tabs styling */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                border-bottom: 1px solid #E2E8F0;
            }
            .stTabs [data-baseweb="tab"] {
                padding: 8px 16px;
                font-weight: 600;
                color: #64748B;
            }
            .stTabs [aria-selected="true"] {
                color: #1E3A8A !important;
                border-bottom-color: #1E3A8A !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(title: str, value: Any, subtitle: str = ""):
    """Render a clean white KPI metric card."""
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