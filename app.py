import streamlit as st
import pandas as pd
import os
from src.engine import run_sla_audit, get_filtered_raw, get_date_range, get_performance_summary, process_sla_upload

st.set_page_config(page_title="SLA Price Tracker", page_icon="📊", layout="wide")
st.title("📊 SLA Price Tracker")

# --- Sidebar: SLA Upload ---
with st.sidebar:
    st.header("⚙️ Configuration")
    uploaded_sla = st.file_uploader("Upload Master SLA Targets (Excel)", type=['xlsx'])
    sla_data = process_sla_upload(uploaded_sla) if uploaded_sla else None
    if sla_data:
        st.success("✅ Targets Loaded")
        st.table(pd.DataFrame([{"Segment": k, "Count": len(v)} for k, v in sla_data.items()]))
    else:
        st.warning("Please upload Target Excel.")

# --- Session State ---
if 'audit_results' not in st.session_state:
    st.session_state.update({'audit_results': None, 'date_range': ("N/A", "N/A"), 'mapping': None})

def validate_columns(df):
    mapping = {'biz segment': 'Biz Segment', 'category': 'Category', 'debit amt': 'Debit Amt', 'gross margin': 'Gross Margin', 'time created': 'Time Created'}
    actual_cols = {c.strip().lower(): c for c in df.columns}
    missing = [mapping[r] for r in mapping if r not in actual_cols]
    if not missing:
        return df.rename(columns={actual_cols[k]: v for k, v in mapping.items() if k in actual_cols}), []
    return df, missing

# --- Main UI ---
st.subheader("1. Upload Sales Data")
uploaded_sales = st.file_uploader("Upload Sales CSV", type="csv")

if uploaded_sales and sla_data:
    sales_df = pd.read_csv(uploaded_sales)
    sales_df, missing_cols = validate_columns(sales_df)
    
    if not missing_cols:
        st.info("💡 Map the columns from your CSV:")
        c1, c2 = st.columns(2)
        with c1:
            corp_col = st.selectbox("Corporate Name Column", sales_df.columns, index=sales_df.columns.get_loc('Name') if 'Name' in sales_df.columns else 0)
        with c2:
            retail_col = st.selectbox("Retail/SMB Channel Column", sales_df.columns, index=sales_df.columns.get_loc('Disbursement Channel Name') if 'Disbursement Channel Name' in sales_df.columns else 0)
        
        mapping = {'Corporate': corp_col, 'Retail': retail_col, 'SMB': retail_col}

        if st.button("🚀 Run Segmented Audit", type="primary"):
            results = run_sla_audit(sales_df, sla_data, col_mapping=mapping)
            start, end = get_date_range(sales_df)
            st.session_state.update({'audit_results': results, 'date_range': (start, end), 'mapping': mapping})
    else:
        st.error(f"⚠️ Missing Columns: {', '.join(missing_cols)}")

# --- Results Display ---
if st.session_state.audit_results is not None:
    results, (start_date, end_date), active_map = st.session_state.audit_results, st.session_state.date_range, st.session_state.mapping
    date_str = f"{start_date}_to_{end_date}"
    
    st.markdown("### 2. Performance Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    total_debit, total_margin = results['Debit Amt'].sum(), results['Gross Margin'].sum()
    m1.metric("Start Date", start_date); m2.metric("End Date", end_date)
    m3.metric("Total Debit", f"{total_debit:,.2f}"); m4.metric("Total Margin", f"{total_margin:,.2f}")
    m5.metric("Global Margin %", f"{(total_margin/total_debit if total_debit else 0):.2%}")

    st.markdown("---")
    tabs = st.tabs(["🌎 All", "🏢 Corporate", "🏪 Retail", "📈 SMB"])
    
    def render(df, n):
        if df.empty: return st.info(f"No data for {n}")
        cols = ['Biz Segment', 'Category', 'Entity_Name', 'Debit Amt', 'Gross Margin', 'Margin %', 'SLA_Target', 'Variance', 'Status']
        existing = [c for c in cols if c in df.columns]
        
        styled = df[existing].style.format({
            'Debit Amt': '{:,.2f}', 'Gross Margin': '{:,.2f}', 
            'Margin %': '{:.2%}', 'SLA_Target': '{:.2%}', 'Variance': '{:+.2%}'
        }, na_rep="-").map(
            lambda x: 'color: red; font-weight: bold' if x == 'F' else 
                      'color: green; font-weight: bold' if x == 'P' else 
                      'color: orange; font-weight: bold' if x == 'NT' else '', 
            subset=['Status']
        )
        st.dataframe(styled, use_container_width=True)

    with tabs[0]: render(results, "All")
    for i, seg in enumerate(['Corporate', 'Retail', 'SMB']):
        with tabs[i+1]: render(results[results['Biz Segment'] == seg], seg)

    st.write("### 🛠️ Raw Transaction Exports")
    c_ex1, c_ex2 = st.columns(2)
    with c_ex1:
        fail_df = get_filtered_raw(sales_df, results, "F", col_mapping=active_map)
        if not fail_df.empty: st.download_button(f"🚩 Download {len(fail_df)} Fails", fail_df.to_csv(index=False), f"Fails_{date_str}.csv")
    with c_ex2:
        nt_df = get_filtered_raw(sales_df, results, "NT", col_mapping=active_map)
        if not nt_df.empty: st.download_button("🔍 Download No Target List", nt_df.to_csv(index=False), f"Update_Excel_{date_str}.csv")