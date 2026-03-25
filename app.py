import streamlit as st
import pandas as pd
from src.data_loader import load_all_slas, process_sales_data
from src.engine import run_sla_audit, get_failed_transactions, get_date_range

st.set_page_config(page_title="SLA Price Tracker", page_icon="📊", layout="wide")

st.title("📊 SLA Price Tracker")
st.markdown("---")

# Session State Initialization
if 'audit_results' not in st.session_state:
    st.session_state.audit_results = None
if 'date_range' not in st.session_state:
    st.session_state.date_range = ("N/A", "N/A")

SLA_FILE = "config/sla_targets.xlsx"
sla_data = load_all_slas(SLA_FILE)

if sla_data:
    st.sidebar.success("✅ SLA Configuration Loaded")
    st.sidebar.info("🎯 Logic: 10% Relative Tolerance (10% of Target Value)")
else:
    st.sidebar.error("❌ SLA Configuration Missing")

st.subheader("1. Upload Sales Data")
uploaded_file = st.file_uploader("Upload Sales CSV", type="csv")

if uploaded_file and sla_data:
    sales_df = process_sales_data(uploaded_file)
    
    if sales_df is not None:
        if st.button("🚀 Run Segmented Audit"):
            with st.spinner("Calculating Relative Deviations..."):
                results = run_sla_audit(sales_df, sla_data)
                start, end = get_date_range(sales_df)
                st.session_state.audit_results = results
                st.session_state.date_range = (start, end)

        if st.session_state.audit_results is not None:
            results = st.session_state.audit_results
            start_date, end_date = st.session_state.date_range
            date_str = f"{start_date}_to_{end_date}"
            
            # 1. Performance Summary
            st.markdown("### 2. Performance Summary")
            m1, m2, m3, m4, m5 = st.columns(5)
            total_debit = results['Debit Amt'].sum()
            total_margin = results['Gross Margin'].sum()
            overall_margin = total_margin / total_debit if total_debit != 0 else 0
            
            m1.metric("Start Date", start_date)
            m2.metric("End Date", end_date)
            m3.metric("Total Debit", f"{total_debit:,.3f}")
            m4.metric("Total Margin", f"{total_margin:,.3f}")
            m5.metric("Global Margin %", f"{overall_margin:.3f}")

            st.markdown("---")
            
            # 2. Audit Reports
            st.subheader("3. Audit Reports by Business Segment")
            tab_all, tab_corp, tab_retail, tab_smb = st.tabs(["🌎 All", "🏢 Corporate", "🏪 Retail", "📈 SMB"])

            def render_table(df, name):
                if df.empty:
                    st.info(f"No data for {name}")
                    return
                
                cols = ['Biz Segment', 'Category', 'Name', 'Disbursement Channel Name', 
                        'Debit Amt', 'Gross Margin', 'Margin %', 'SLA_Target', 'Variance', 'Status']
                existing = [c for c in cols if c in df.columns]
                
                # Updated .map() to replace deprecated .applymap()
                styled = df[existing].style.format({
                    'Debit Amt': '{:,.3f}', 'Gross Margin': '{:,.3f}', 
                    'Margin %': '{:.3f}', 'SLA_Target': '{:.3f}', 'Variance': '{:+.3f}'
                }).map(
                    lambda x: 'color: red; font-weight: bold' if x == 'Fail' else 'color: green; font-weight: bold' if x == 'Pass' else '', 
                    subset=['Status']
                )
                
                # Updated width='stretch' to replace deprecated use_container_width
                st.dataframe(styled, width="stretch")
                st.download_button(label=f"📥 Download {name} Pivot", data=df.to_csv(index=False), file_name=f"SLA_Audit_{name}_{date_str}.csv", mime="text/csv", key=f"dl_{name}")

            with tab_all: render_table(results, "All_Segments")
            with tab_corp: render_table(results[results['Biz Segment'] == 'Corporate'], "Corporate")
            with tab_retail: render_table(results[results['Biz Segment'] == 'Retail'], "Retail")
            with tab_smb: render_table(results[results['Biz Segment'] == 'SMB'], "SMB")

            # 3. Failure Alert and Download (AFTER the table)
            st.markdown("---")
            failed_rows = results[results['Status'] == 'Fail']
            if not failed_rows.empty:
                st.warning(f"⚠️ {len(failed_rows)} Categories outside the 10% relative tolerance.")
                failed_raw_data = get_failed_transactions(sales_df, results)
                st.download_button(label="🚩 DOWNLOAD FAILED RAW TRANSACTIONS", data=failed_raw_data.to_csv(index=False), file_name=f"FAILED_TRANSACTIONS_{date_str}.csv", mime="text/csv", key="dl_failed")
            else:
                st.success("🎉 All categories are within the 10% relative tolerance.")
    else:
        st.error("Invalid CSV uploaded.")