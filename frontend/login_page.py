import streamlit as st

from backend.auth import authenticate_user
from frontend.theme import apply_custom_theme


def render_login_page():
    """Render a clean, production-grade login interface."""
    apply_custom_theme()

    col1, col2, col3 = st.columns([1, 1.4, 1])

    with col2:
        st.markdown(
            """
            <div style="text-align: center; margin-top: 55px; margin-bottom: 28px;">
                <h1 style="color: #0F172A; font-size: 1.75rem; font-weight: 700; letter-spacing: -0.025em; margin-bottom: 6px;">
                    Inventory Management
                </h1>
                <p style="color: #64748B; font-size: 0.9rem; margin: 0; font-weight: 400;">
                    Near-Expiry Stock Recovery & Decision Support System
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown(
                "<div style='font-size: 1.1rem; font-weight: 600; color: #0F172A; margin-bottom: 14px;'>Sign In</div>",
                unsafe_allow_html=True,
            )

            username_input = st.text_input(
                "Username",
                placeholder="Enter username",
            )
            password_input = st.text_input(
                "Password",
                type="password",
                placeholder="Enter password",
            )

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            submit = st.button("Sign In", use_container_width=True)

            if submit:
                if not username_input or not password_input:
                    st.warning("Please enter both username and password.")
                else:
                    user = authenticate_user(username_input, password_input)
                    if user:
                        st.session_state["current_user"] = user
                        st.session_state["page"] = "Dashboard"
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Please verify your username and password.")