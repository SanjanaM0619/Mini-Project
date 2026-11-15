import streamlit as st

from backend.auth import seed_branches_and_demo_users
from backend.database import initialize_database
from backend.seed_data import seed_all_demo_data
from frontend.login_page import render_login_page
from frontend.theme import apply_custom_theme

st.set_page_config(
    page_title="DMart Retail DSS",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure database and seed data exist
initialize_database()
seed_all_demo_data()


def main():
    apply_custom_theme()

    if "current_user" not in st.session_state:
        st.session_state["current_user"] = None

    user = st.session_state["current_user"]

    # 1. If not logged in, show Login Screen
    if user is None:
        render_login_page()
        return

    # 2. Sidebar Navigation for Logged-In Users
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding: 10px 0 20px 0;">
                <h3 style="color: #1E3A8A; margin: 0;">DMart Retail DSS</h3>
                <p style="color: #64748B; font-size: 0.85rem; margin: 0;">Near-Expiry Recovery</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div style="background: #F1F5F9; padding: 12px; border-radius: 8px; margin-bottom: 20px;">
                <div style="font-weight: 700; color: #0F172A;">{user['full_name']}</div>
                <div style="font-size: 0.8rem; color: #475569;">Role: <b>{user['role'].upper()}</b></div>
                <div style="font-size: 0.8rem; color: #475569;">Branch: <b>{user['branch_name']}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        page = st.radio(
            "Navigation",
            [
                "📊 Overview Dashboard",
                "📦 Inventory Management",
                "📈 Daily Sales Records",
                "🎯 Recovery & Monte Carlo",
                "🔄 Inter-Branch Transfers",
            ],
            key="selected_page",
        )

        st.markdown("<hr style='margin: 25px 0 15px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state["current_user"] = None
            st.rerun()

    # Placeholder router for next pages
    if "Overview Dashboard" in page:
        st.header("📊 Overview Dashboard")
        st.info("Dashboard module will load here next.")
    elif "Inventory Management" in page:
        st.header("📦 Inventory Management")
        st.info("Inventory batches module will load here.")
    elif "Daily Sales Records" in page:
        st.header("📈 Daily Sales Records")
        st.info("Daily sales module will load here.")
    elif "Recovery & Monte Carlo" in page:
        st.header("🎯 Near-Expiry Recovery & Monte Carlo Simulation")
        st.info("Monte Carlo decision engine module will load here.")
    elif "Inter-Branch Transfers" in page:
        st.header("🔄 Inter-Branch Transfer Workflow")
        st.info("Transfer requests module will load here.")


if __name__ == "__main__":
    main()