"""
SLA Price Tracker - Main Streamlit Application

This application allows users to upload sales data and audit it against 
pre-defined SLA (Service Level Agreement) targets stored in an Excel configuration file.
It provides performance summaries, segmented results (Corporate, Retail, SMB), 
and export options for audit results and transaction logs.
"""

import streamlit as st
import pandas as pd
import os
from src.data_loader import load_all_slas, process_sales_data
from src.engine import run_sla_audit, get_filtered_raw, get_date_range, get_performance_summary

# --- Page Configuration ---
st.set_page_config(page_title="SLA Price Tracker", page_icon="📊", layout="wide")
st.title("📊 SLA Price Tracker")

# --- Constants and Paths ---
base_path = os.path.dirname(os.path.abspath(__file__))
SLA_FILE = os.path.join(base_path, "config", "sla_targets.xlsx")

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    if st.button("🔄 Reload Excel Config"):
        st.cache_data.clear()
        st.success("Cache Cleared!")
        st.rerun()

    # Load SLA targets from the Excel file
    sla_data = load_all_slas(SLA_FILE)
    if sla_data:
        st.success("✅ Targets Loaded")
        # Display a summary of loaded targets
        counts = [{"Segment": k, "Count": len(v)} for k, v in sla_data.items()]
        st.write("**Current SLA Counts:**")
        st.table(pd.DataFrame(counts))

# --- Session State Management ---
# Initialize session state for storing audit results persistent across reruns
if 'audit_results' not in st.session_state:
    st.session_state.update({'audit_results': None, 'date_range': ("N/A", "N/A")})

def validate_columns(df):
    """
    Validates that the required columns exist in the uploaded sales data.
    
    Args:
        df (pd.DataFrame): The sales data to validate.
        
    Returns:
        list: A list of missing column names.
    """
    req = ['Biz Segment', 'Category', 'Debit Amt', 'Gross Margin', 'Time Created']
    missing = [c for c in req if c not in df.columns]
    
    # Check for either Name or Disbursement Channel Name
    if 'Name' not in df.columns and 'Disbursement Channel Name' not in df.columns:
        missing.append("Name/Disbursement Channel Name")
    return missing

# --- 1. Data Upload Section ---
st.subheader("1. Upload Sales Data")
uploaded_file = st.file_uploader("Upload Sales CSV", type="csv")

if uploaded_file and sla_data:
    # Process the uploaded file
    sales_df = process_sales_data(uploaded_file)
    if sales_df is not None:
        missing_cols = validate_columns(sales_df)
        if not missing_cols:
            # Trigger the audit process
            if st.button("🚀 Run Segmented Audit"):
                results = run_sla_audit(sales_df, sla_data)
                start, end = get_date_range(sales_df)
                # Store results in session state
                st.session_state.update({'audit_results': results, 'date_range': (start, end)})
        else:
            st.error(f"Missing Columns: {', '.join(missing_cols)}")

        # --- 2. Results Display Section ---
        if st.session_state.audit_results is not None:
            results = st.session_state.audit_results
            start_date, end_date = st.session_state.date_range
            date_str = f"{start_date}_to_{end_date}"
            
            # --- Performance Summary Metrics ---
            st.markdown("### 2. Performance Summary")
            m1, m2, m3, m4, m5 = st.columns(5)
            total_debit = results['Debit Amt'].sum()
            total_margin = results['Gross Margin'].sum()
            m1.metric("Start Date", start_date)
            m2.metric("End Date", end_date)
            m3.metric("Total Debit", f"{total_debit:,.2f}")
            m4.metric("Total Margin", f"{total_margin:,.2f}")
            m5.metric("Global Margin %", f"{(total_margin/total_debit if total_debit else 0):.3f}")

            # --- Export Results Row ---
            st.write("### 📂 Export Results")
            dl_col1, dl_col2 = st.columns(2)
            
            with dl_col1:
                # Performance summary by segment
                perf_df = get_performance_summary(results)
                st.download_button(
                    label="📥 Download Performance Summary",
                    data=perf_df.to_csv(index=False),
                    file_name=f"Performance_Summary_{date_str}.csv",
                    mime="text/csv"
                )
            
            with dl_col2:
                # Full calculated audit results
                st.download_button(
                    label="📥 Download Audit Pivot (Calculated Results)",
                    data=results.to_csv(index=False),
                    file_name=f"Audit_Pivot_Results_{date_str}.csv",
                    mime="text/csv"
                )

            st.markdown("---")
            # --- Results Dataframes Tabs ---
            tabs = st.tabs(["🌎 All", "🏢 Corporate", "🏪 Retail", "📈 SMB"])
            
            def render(df, n):
                """
                Helper function to render the results dataframe with styling.
                """
                if df.empty: return st.info(f"No data for {n}")
                
                # Filter to columns that exist in the dataframe
                cols = ['Biz Segment', 'Category', 'Name', 'Disbursement Channel Name', 
                        'Debit Amt', 'Gross Margin', 'Margin %', 'SLA_Target', 'Variance', 'Status']
                existing = [c for c in cols if c in df.columns]
                
                # Apply styling to the dataframe
                styled = df[existing].style.format({
                    'Debit Amt': '{:,.2f}', 
                    'Gross Margin': '{:,.2f}', 
                    'Margin %': '{:.3f}', 
                    'SLA_Target': '{:.3f}', 
                    'Variance': '{:+.3f}'
                }, na_rep="-").map(
                    lambda x: 'color: red; font-weight: bold' if x == 'Fail' else 
                              'color: green; font-weight: bold' if x == 'Pass' else 
                              'color: orange; font-weight: bold' if x == 'No Target' else '', 
                    subset=['Status']
                )
                st.dataframe(styled, use_container_width=True)

            # Populate tabs with corresponding segment data
            with tabs[0]: render(results, "All")
            with tabs[1]: render(results[results['Biz Segment'] == 'Corporate'], "Corporate")
            with tabs[2]: render(results[results['Biz Segment'] == 'Retail'], "Retail")
            with tabs[3]: render(results[results['Biz Segment'] == 'SMB'], "SMB")

            st.markdown("---")
            # --- Raw Data Exports Section ---
            st.write("### 🛠️ Raw Transaction Exports")
            c1, c2 = st.columns(2)
            with c1:
                # Filter for failed transactions
                fail_df = get_filtered_raw(sales_df, results, "Fail")
                if not fail_df.empty:
                    st.warning(f"🚩 Found {len(fail_df)} failed transactions.")
                    st.download_button("📥 Download Fails Raw Data", fail_df.to_csv(index=False), f"Fails_{date_str}.csv")
            with c2:
                # Filter for transactions with no SLA target
                nt_df = get_filtered_raw(sales_df, results, "No Target")
                if not nt_df.empty:
                    st.info(f"🔍 Found {len(nt_df)} transactions with no target.")
                    # Export a unique list of missing category/name pairs for config update
                    clean_nt = nt_df[['Biz Segment', 'Category', 'Name', 'Disbursement Channel Name']].drop_duplicates()
                    st.download_button("📥 Download No Target List", clean_nt.to_csv(index=False), f"Update_Excel_{date_str}.csv")