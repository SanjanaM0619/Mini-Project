import streamlit as st

from backend.auth import seed_branches_and_demo_users
from backend.database import initialize_database
from backend.seed_data import seed_all_demo_data
from frontend.login_page import render_login_page
from frontend.theme import apply_custom_theme
from frontend.dashboard_page import render_dashboard_page

st.set_page_config(
    page_title="Inventory Management",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Ensure database and seed data exist
initialize_database()
seed_all_demo_data()


def render_top_header(user):
    """Render a perfectly aligned top header bar."""
    col_brand, col_user = st.columns([2.5, 1.5], vertical_alignment="center")

    with col_brand:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.35rem; font-weight: 700; color: #0F172A; letter-spacing: -0.02em;">
                    Inventory Management
                </span>
                <span style="font-size: 0.78rem; font-weight: 600; color: #475569; background: #F1F5F9; border: 1px solid #E2E8F0; padding: 3px 10px; border-radius: 14px;">
                    {user['branch_name']}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_user:
        u_info, u_btn = st.columns([2.4, 1], vertical_alignment="center")
        with u_info:
            st.markdown(
                f"""
                <div style="text-align: right; line-height: 1.25;">
                    <div style="font-size: 0.86rem; font-weight: 600; color: #0F172A;">{user['full_name']}</div>
                    <div style="font-size: 0.72rem; color: #64748B; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;">{user['role']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with u_btn:
            if st.button("Sign Out", key="top_sign_out", use_container_width=True):
                st.session_state["current_user"] = None
                st.rerun()


def main():
    apply_custom_theme()

    if "current_user" not in st.session_state:
        st.session_state["current_user"] = None

    user = st.session_state["current_user"]

    # 1. Login Screen if not authenticated
    if user is None:
        render_login_page()
        return

    # 2. Top Header (Brand on Left, User & Sign Out on Right)
    render_top_header(user)

    # 3. Clean Stripe/GitHub style tab navigation
    (
        tab_overview,
        tab_inventory,
        tab_sales,
        tab_decision,
        tab_transfers,
    ) = st.tabs(
        [
            "Overview",
            "Inventory",
            "Daily Sales",
            "Decision Engine",
            "Transfers",
        ]
    )

    with tab_overview:
        render_dashboard_page(user)

    with tab_inventory:
        st.markdown("<h3 style='font-size: 1.25rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Inventory Management</h3>", unsafe_allow_html=True)
        st.info("Inventory batches module will load here.")

    with tab_sales:
        st.markdown("<h3 style='font-size: 1.25rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Daily Sales Records</h3>", unsafe_allow_html=True)
        st.info("Daily sales module will load here.")

    with tab_decision:
        st.markdown("<h3 style='font-size: 1.25rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Near-Expiry Recovery & Monte Carlo Decision Engine</h3>", unsafe_allow_html=True)
        st.info("Monte Carlo decision engine module will load here.")

    with tab_transfers:
        st.markdown("<h3 style='font-size: 1.25rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Inter-Branch Transfers</h3>", unsafe_allow_html=True)
        st.info("Transfer requests module will load here.")


if __name__ == "__main__":
    main()