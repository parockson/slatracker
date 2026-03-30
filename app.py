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

    sla_data = load_all_slas(SLA_FILE)
    if sla_data:
        st.success("✅ Targets Loaded")
        counts = [{"Segment": k, "Count": len(v)} for k, v in sla_data.items()]
        st.write("**Current SLA Counts:**")
        st.table(pd.DataFrame(counts))
    else:
        st.error("❌ SLA Config Not Found at config/sla_targets.xlsx")

# --- Session State Management ---
if 'audit_results' not in st.session_state:
    st.session_state.update({'audit_results': None, 'date_range': ("N/A", "N/A")})

def validate_and_fix_columns(df):
    """Checks for required columns and renames them if they have spaces/wrong casing."""
    # Mapping of expected names (lowercase) to the actual required names
    mapping = {
        'biz segment': 'Biz Segment',
        'category': 'Category',
        'debit amt': 'Debit Amt',
        'gross margin': 'Gross Margin',
        'time created': 'Time Created',
        'name': 'Name',
        'disbursement channel name': 'Disbursement Channel Name'
    }
    
    # Standardize current columns: trim spaces and lowercase for comparison
    current_cols = {c.strip().lower(): c for c in df.columns}
    
    # Check for basic requirements
    required_base = ['biz segment', 'category', 'debit amt', 'gross margin', 'time created']
    missing = [mapping[r] for r in required_base if r not in current_cols]
    
    if 'name' not in current_cols and 'disbursement channel name' not in current_cols:
        missing.append("Name or Disbursement Channel Name")
    
    if not missing:
        # Automatically rename columns to the exact casing the engine expects
        rename_map = {current_cols[k]: mapping[k] for k in current_cols if k in mapping}
        df = df.rename(columns=rename_map)
        return df, []
    
    return df, missing

# --- 1. Data Upload Section ---
st.subheader("1. Upload Sales Data")
uploaded_file = st.file_uploader("Upload Sales CSV", type="csv")

if uploaded_file and sla_data:
    sales_df = process_sales_data(uploaded_file)
    
    if sales_df is not None:
        # Validate and auto-fix column naming/casing
        sales_df, missing_cols = validate_and_fix_columns(sales_df)
        
        if not missing_cols:
            st.success("✅ CSV Format Validated")
            # --- THE RUN BUTTON ---
            if st.button("🚀 Run Segmented Audit", type="primary"):
                with st.spinner("Analyzing margins..."):
                    results = run_sla_audit(sales_df, sla_data)
                    start, end = get_date_range(sales_df)
                    st.session_state.update({'audit_results': results, 'date_range': (start, end)})
        else:
            st.error(f"⚠️ Missing or Incorrect Columns: {', '.join(missing_cols)}")
            st.info("Please ensure your CSV includes: Biz Segment, Category, Debit Amt, Gross Margin, Time Created, and Name.")

        # --- 2. Results Display Section ---
        if st.session_state.audit_results is not None:
            results = st.session_state.audit_results
            start_date, end_date = st.session_state.date_range
            date_str = f"{start_date}_to_{end_date}"
            
            st.markdown("### 2. Performance Summary")
            m1, m2, m3, m4, m5 = st.columns(5)
            total_debit = results['Debit Amt'].sum()
            total_margin = results['Gross Margin'].sum()
            m1.metric("Start Date", start_date)
            m2.metric("End Date", end_date)
            m3.metric("Total Debit", f"{total_debit:,.2f}")
            m4.metric("Total Margin", f"{total_margin:,.2f}")
            m5.metric("Global Margin %", f"{(total_margin/total_debit if total_debit else 0):.3f}")

            st.write("### 📂 Export Results")
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                perf_df = get_performance_summary(results)
                st.download_button("📥 Download Performance Summary", perf_df.to_csv(index=False), f"Summary_{date_str}.csv", "text/csv")
            with dl_col2:
                st.download_button("📥 Download Audit Pivot (Calculated)", results.to_csv(index=False), f"Audit_Pivot_{date_str}.csv", "text/csv")

            st.markdown("---")
            tabs = st.tabs(["🌎 All", "🏢 Corporate", "🏪 Retail", "📈 SMB"])
            
            def render(df, n):
                if df.empty: return st.info(f"No data for {n}")
                cols = ['Biz Segment', 'Category', 'Name', 'Disbursement Channel Name', 'Debit Amt', 'Gross Margin', 'Margin %', 'SLA_Target', 'Variance', 'Status']
                existing = [c for c in cols if c in df.columns]
                styled = df[existing].style.format({'Debit Amt': '{:,.2f}', 'Gross Margin': '{:,.2f}', 'Margin %': '{:.3f}', 'SLA_Target': '{:.3f}', 'Variance': '{:+.3f}'}, na_rep="-").map(
                    lambda x: 'color: red; font-weight: bold' if x == 'Fail' else 
                              'color: green; font-weight: bold' if x == 'Pass' else 
                              'color: orange; font-weight: bold' if x == 'No Target' else '', subset=['Status']
                )
                st.dataframe(styled, use_container_width=True)

            with tabs[0]: render(results, "All")
            with tabs[1]: render(results[results['Biz Segment'] == 'Corporate'], "Corporate")
            with tabs[2]: render(results[results['Biz Segment'] == 'Retail'], "Retail")
            with tabs[3]: render(results[results['Biz Segment'] == 'SMB'], "SMB")

            st.markdown("---")
            st.write("### 🛠️ Raw Transaction Exports")
            c1, c2 = st.columns(2)
            with c1:
                fail_df = get_filtered_raw(sales_df, results, "Fail")
                if not fail_df.empty:
                    st.warning(f"🚩 Found {len(fail_df)} failed transactions.")
                    st.download_button("📥 Download Fails Raw Data", fail_df.to_csv(index=False), f"Fails_{date_str}.csv")
            with c2:
                nt_df = get_filtered_raw(sales_df, results, "No Target")
                if not nt_df.empty:
                    st.info(f"🔍 Found {len(nt_df)} transactions with no target.")
                    clean_nt = nt_df[['Biz Segment', 'Category', 'Name', 'Disbursement Channel Name']].drop_duplicates()
                    st.download_button("📥 Download No Target List", clean_nt.to_csv(index=False), f"Update_Excel_{date_str}.csv")