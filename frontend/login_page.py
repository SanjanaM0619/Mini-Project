import streamlit as st

from backend.auth import authenticate_user
from frontend.theme import apply_custom_theme


def render_login_page():
    """Render a clean, corporate login interface with clearly marked demo credentials."""
    apply_custom_theme()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            """
            <div style="text-align: center; margin-top: 30px; margin-bottom: 25px;">
                <h1 style="color: #1E3A8A; font-size: 2rem; margin-bottom: 6px;">DMart Retail DSS</h1>
                <p style="color: #64748B; font-size: 1rem; margin: 0;">
                    Near-Expiry Inventory Recovery Decision Support System
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.subheader("Sign In")

            username_input = st.text_input("Username", placeholder="e.g. admin or hk_manager")
            password_input = st.text_input("Password", type="password", placeholder="Enter your password")

            submit = st.button("Log In", use_container_width=True)

            if submit:
                if not username_input or not password_input:
                    st.warning("Please enter both username and password.")
                else:
                    user = authenticate_user(username_input, password_input)
                    if user:
                        st.session_state["current_user"] = user
                        st.session_state["page"] = "Dashboard"
                        st.success(f"Welcome, {user['full_name']}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password. Please check credentials.")

        # Clearly marked demonstration credentials
        with st.expander("🔑 Demonstration Test Credentials (Click to view)", expanded=False):
            st.markdown(
                """
                **Main Administrator** (Full cross-branch access):
                * Username: `admin` | Password: `Admin@123`

                **Branch Managers** (Restricted to assigned branch only):
                * Hampankatta: `hk_manager` | Password: `Branch@123`
                * Kadri: `kd_manager` | Password: `Branch@123`
                * Bejai: `bj_manager` | Password: `Branch@123`
                * Kankanady: `kk_manager` | Password: `Branch@123`
                * Urwa: `ur_manager` | Password: `Branch@123`
                """
            )