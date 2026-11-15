import streamlit as st

from backend.auth import seed_branches_and_demo_users
from backend.database import initialize_database
from backend.seed_data import seed_all_demo_data
from frontend.login_page import render_login_page
from frontend.theme import apply_custom_theme

st.set_page_config(
    page_title="Inventory Management",
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
            <div style="padding: 10px 0 16px 0;">
                <div style="font-size: 1.1rem; font-weight: 700; color: #0F172A; letter-spacing: -0.015em;">
                    Inventory Management
                </div>
                <div style="font-size: 0.75rem; color: #64748B; margin-top: 2px;">
                    Near-Expiry Decision System
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; padding: 12px 14px; border-radius: 6px; margin-bottom: 20px;">
                <div style="font-weight: 600; font-size: 0.88rem; color: #0F172A;">{user['full_name']}</div>
                <div style="font-size: 0.78rem; color: #475569; margin-top: 2px;">
                    Role: <span style="font-weight: 600; color: #0F172A;">{user['role'].upper()}</span>
                </div>
                <div style="font-size: 0.78rem; color: #475569;">
                    Branch: <span style="font-weight: 600; color: #0F172A;">{user['branch_name']}</span>
                </div>
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
            label_visibility="collapsed",
        )

        st.markdown("<hr style='margin: 24px 0 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

        if st.button("Sign Out", use_container_width=True):
            st.session_state["current_user"] = None
            st.rerun()

    # Router
    if "Overview Dashboard" in page:
        st.markdown("<h2 style='font-size: 1.5rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Overview Dashboard</h2>", unsafe_allow_html=True)
        st.info("Dashboard module will load here.")
    elif "Inventory Management" in page:
        st.markdown("<h2 style='font-size: 1.5rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Inventory Management</h2>", unsafe_allow_html=True)
        st.info("Inventory batches module will load here.")
    elif "Daily Sales Records" in page:
        st.markdown("<h2 style='font-size: 1.5rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Daily Sales Records</h2>", unsafe_allow_html=True)
        st.info("Daily sales module will load here.")
    elif "Recovery & Monte Carlo" in page:
        st.markdown("<h2 style='font-size: 1.5rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Near-Expiry Recovery & Monte Carlo</h2>", unsafe_allow_html=True)
        st.info("Monte Carlo decision engine module will load here.")
    elif "Inter-Branch Transfers" in page:
        st.markdown("<h2 style='font-size: 1.5rem; font-weight: 700; color: #0F172A; margin-bottom: 8px;'>Inter-Branch Transfers</h2>", unsafe_allow_html=True)
        st.info("Transfer requests module will load here.")


if __name__ == "__main__":
    main()