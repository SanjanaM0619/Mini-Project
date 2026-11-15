from datetime import date
from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st

from backend.inventory import get_expiry_summary, get_inventory
from frontend.theme import render_kpi


def render_dashboard_page(user: Dict[str, Any]):
    """Render the executive Overview Dashboard with uniform cards and clear X/Y axes."""
    role = user.get("role", "manager")

    # 1. Branch Filter for Admin
    selected_branch = "ALL"
    if role == "admin":
        col_title, col_filter = st.columns([3, 1], vertical_alignment="center")
        with col_title:
            st.markdown(
                "<div style='font-size: 1.15rem; font-weight: 700; color: #0F172A;'>Store-Wide Health & Near-Expiry Status</div>",
                unsafe_allow_html=True,
            )
        with col_filter:
            selected_branch = st.selectbox(
                "Filter Branch",
                ["ALL", "HK", "KD", "BJ", "KK", "UR"],
                label_visibility="collapsed",
                key="dash_branch_filter",
            )
    else:
        st.markdown(
            f"<div style='font-size: 1.15rem; font-weight: 700; color: #0F172A;'>{user['branch_name']} — Inventory Health & Expiry Status</div>",
            unsafe_allow_html=True,
        )

    # 2. Fetch live database inventory
    batches = get_inventory(user, branch_filter=selected_branch)
    summary = get_expiry_summary(batches)

    # Calculate estimated potential recovery value
    active_batches = [b for b in batches if b["quantity"] > 0 and b["days_left"] >= 0]
    total_recovery_val = sum(b["quantity"] * b["selling_price"] for b in active_batches)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 3. 6 Uniform Key Metrics (Every card has identical height and subtitle layout)
    kpi_cols = st.columns(6)
    with kpi_cols[0]:
        render_kpi("Total Batches", summary["total_batches"], "Across catalog")
    with kpi_cols[1]:
        render_kpi("Total Units", f"{summary['total_units']:,}", "Active stock units")
    with kpi_cols[2]:
        render_kpi("At-Risk (≤30d)", summary["at_risk_batches"], f"{summary['at_risk_units']:,} units")
    with kpi_cols[3]:
        render_kpi("Critical (≤3d)", summary["critical_batches"], "Needs action")
    with kpi_cols[4]:
        render_kpi("Expired Batches", summary["expired_batches"], f"{summary['expired_units']:,} units")
    with kpi_cols[5]:
        render_kpi("Stock Value", f"₹{total_recovery_val:,.0f}", "Sellable inventory")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    if not batches:
        st.info("No inventory batches recorded.")
        return

    df = pd.DataFrame(batches)

    # 4. Interactive Plotly Charts with explicit X & Y axes
    chart_cols = st.columns(2)

    with chart_cols[0]:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size: 0.92rem; font-weight: 600; color: #0F172A; margin-bottom: 12px;'>Batch Shelf-Life Risk Distribution</div>",
            unsafe_allow_html=True,
        )
        status_counts = df["expiry_status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Batches"]

        color_map = {
            "Safe (>30d)": "#166534",
            "At-Risk (4-30d)": "#D97706",
            "Critical (<=3d)": "#DC2626",
            "Expired": "#64748B",
        }

        fig_status = px.bar(
            status_counts,
            x="Status",
            y="Batches",
            color="Status",
            color_discrete_map=color_map,
            text="Batches",
        )
        fig_status.update_layout(
            margin=dict(l=40, r=20, t=10, b=40),
            height=300,
            showlegend=False,
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            xaxis=dict(
                title=dict(text="Expiry Risk Category", font=dict(size=12, color="#475569")),
                showline=True,
                linecolor="#CBD5E1",
                tickfont=dict(color="#0F172A", size=11),
            ),
            yaxis=dict(
                title=dict(text="Number of Batches", font=dict(size=12, color="#475569")),
                showline=True,
                linecolor="#CBD5E1",
                showgrid=True,
                gridcolor="#F1F5F9",
                tickfont=dict(color="#0F172A", size=11),
            ),
        )
        fig_status.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig_status, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_cols[1]:
        st.markdown("<div class='chart-card'>", unsafe_allow_html=True)
        if role == "admin" and selected_branch == "ALL":
            st.markdown(
                "<div style='font-size: 0.92rem; font-weight: 600; color: #0F172A; margin-bottom: 12px;'>Stock Units Across Mangalore Branches</div>",
                unsafe_allow_html=True,
            )
            branch_units = df.groupby("branch_code")["quantity"].sum().reset_index()
            fig_branch = px.bar(
                branch_units,
                x="branch_code",
                y="quantity",
                text="quantity",
                color_discrete_sequence=["#0F172A"],
            )
            fig_branch.update_layout(
                margin=dict(l=40, r=20, t=10, b=40),
                height=300,
                showlegend=False,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                xaxis=dict(
                    title=dict(text="Branch Code", font=dict(size=12, color="#475569")),
                    showline=True,
                    linecolor="#CBD5E1",
                    tickfont=dict(color="#0F172A", size=11),
                ),
                yaxis=dict(
                    title=dict(text="Total Inventory Units", font=dict(size=12, color="#475569")),
                    showline=True,
                    linecolor="#CBD5E1",
                    showgrid=True,
                    gridcolor="#F1F5F9",
                    tickfont=dict(color="#0F172A", size=11),
                ),
            )
            fig_branch.update_traces(textposition="outside")
            st.plotly_chart(fig_branch, use_container_width=True)
        else:
            st.markdown(
                "<div style='font-size: 0.92rem; font-weight: 600; color: #0F172A; margin-bottom: 12px;'>Available Stock Units by Category</div>",
                unsafe_allow_html=True,
            )
            cat_units = df.groupby("category")["quantity"].sum().reset_index()
            fig_cat = px.bar(
                cat_units,
                x="category",
                y="quantity",
                text="quantity",
                color_discrete_sequence=["#2563EB"],
            )
            fig_cat.update_layout(
                margin=dict(l=40, r=20, t=10, b=40),
                height=300,
                showlegend=False,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
                xaxis=dict(
                    title=dict(text="Product Category", font=dict(size=12, color="#475569")),
                    showline=True,
                    linecolor="#CBD5E1",
                    tickfont=dict(color="#0F172A", size=11),
                ),
                yaxis=dict(
                    title=dict(text="Inventory Units", font=dict(size=12, color="#475569")),
                    showline=True,
                    linecolor="#CBD5E1",
                    showgrid=True,
                    gridcolor="#F1F5F9",
                    tickfont=dict(color="#0F172A", size=11),
                ),
            )
            fig_cat.update_traces(textposition="outside")
            st.plotly_chart(fig_cat, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)