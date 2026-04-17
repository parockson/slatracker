import streamlit as st
import pandas as pd
from src.engine import run_sla_audit, process_sla_upload

# Page Configuration
st.set_page_config(page_title="SLA Audit Engine", layout="wide")
st.title("📊 SLA Audit Engine")

# --- 1. Sidebar: SLA Master Upload ---
with st.sidebar:
    st.header("⚙️ Configuration")
    uploaded_sla = st.file_uploader("Upload SLA Master (Excel)", type=['xlsx'])
    sla_data = process_sla_upload(uploaded_sla) if uploaded_sla else None
    if sla_data:
        st.success(f"✅ SLA Master Loaded ({len(sla_data)} segments)")

# --- 2. Main Page: Sales Data Upload ---
uploaded_sales = st.file_uploader("Upload Daily Sales (CSV)", type="csv")

if uploaded_sales and sla_data:
    # Load and clean CSV headers
    df_raw = pd.read_csv(uploaded_sales)
    df_raw.columns = df_raw.columns.str.strip()
    
    st.divider()
    st.subheader("🛠️ Column Mapping")
    st.info("Assign CSV columns to audit variables. Note: Cor uses 'Debit', Self/Asst uses 'Credit'.")
    
    # Interface for mapping user CSV columns to internal logic
    c1, c2, c3 = st.columns(3)
    with c1:
        seg_col = st.selectbox("Biz Segment Column", df_raw.columns)
        cat_col = st.selectbox("Category Column", df_raw.columns)
    with c2:
        deb_col = st.selectbox("Debit Amt (for Cor)", df_raw.columns)
        cre_col = st.selectbox("Credit Amt (for Self/Asst)", df_raw.columns)
    with c3:
        mar_col = st.selectbox("Gr. Rev(GHC) Column", df_raw.columns)
        
        # Build mapping dictionary for every segment tab
        map_dict = {'segment': seg_col, 'cat': cat_col, 'debit': deb_col, 'credit': cre_col, 'margin': mar_col}
        for tab in sla_data.keys():
            map_dict[tab] = st.selectbox(f"Name Column for '{tab}'", df_raw.columns, key=f"map_{tab}")

    # --- 3. Audit Execution ---
    if st.button("🚀 Run Audit", type="primary"):
        results = run_sla_audit(df_raw, sla_data, map_dict)
        
        if not results.empty:
            st.divider()
            
            # Status Text Color Styling
            def style_status_text(row):
                status = row['Status']
                color = ''
                if status == 'Pass':
                    color = '#28a745'  # Green
                elif status == 'Fail':
                    color = '#dc3545'  # Red
                elif status == 'No Target':
                    color = '#ffc107'  # Gold/Yellow
                
                # Apply color only to the 'Status' column text
                return [f'color: {color}; font-weight: bold' if col == 'Status' else '' for col in row.index]

            # Define display columns and formatting
            disp_cols = ['Biz seg', 'Cat', 'Name', 'Tier', 'Vol', 'Val(GHC)', 'Gr. Rev(GHC)', 'Margin %', 'SLA_Target', 'Var', 'Status']
            
            def render_styled_df(df):
                st.dataframe(
                    df[disp_cols].style.format({
                        'Val(GHC)': '{:,.2f}', 
                        'Gr. Rev(GHC)': '{:,.2f}', 
                        'Margin %': '{:.2%}', 
                        'SLA_Target': '{:.2%}', 
                        'Var': '{:+.2%}'
                    }).apply(style_status_text, axis=1), 
                    use_container_width=True
                )

            # Segment-specific Tabs
            tabs = st.tabs(["🌎 All", "🏢 Cor", "👤 Self", "🤝 Asst"])
            
            with tabs[0]:
                render_styled_df(results)
            with tabs[1]:
                render_styled_df(results[results['Biz seg'] == 'Cor'])
            with tabs[2]:
                render_styled_df(results[results['Biz seg'] == 'Self'])
            with tabs[3]:
                render_styled_df(results[results['Biz seg'] == 'Asst'])
                
            # Download functionality
            csv = results.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Report", data=csv, file_name="SLA_Audit.csv", mime="text/csv")
        else:
            st.error("No data found for the mapped segments. Please check column mapping.")
else:
    st.warning("Please upload both the SLA Master (Excel) and Daily Sales (CSV) to begin.")