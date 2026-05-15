import streamlit as st
import pandas as pd
from src.engine import run_sla_audit, process_sla_upload

def main():
    # ==========================================
    # Page Configuration & Global Setup
    # ==========================================
    st.set_page_config(page_title="SLA Audit Engine", layout="wide", page_icon="📊")

    # --- Custom Styling ---
    # Injects custom CSS to override default Streamlit themes and provide an updated UI
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
        
        /* Defines colour variables for easy themeing */
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --accent-blue: #38bdf8;
            --accent-emerald: #10b981;
            --accent-rose: #f43f5e;
            --text-main: #f8fafc;
            --text-dim: #94a3b8;
        }

        /* Main background */
        .stApp {
            background-color: var(--bg-primary);
            color: var(--text-main);
        }
        
        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--bg-secondary);
            border-right: 1px solid rgba(255,255,255,0.05);
        }

        /* Headers */
        h1, h2, h3 {
            color: var(--text-main) !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }
        
        /* Buttons - adds a premium gradient and hover shadow */
        .stButton>button {
            border-radius: 12px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%);
            color: white;
            border: none;
            padding: 0.6rem 2.5rem;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
            width: 100%;
        }
        
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.4);
            border: none;
            color: white;
        }

        /* Metric Cards - adds rounding and hover effects */
        [data-testid="stMetric"] {
            background-color: var(--bg-secondary);
            padding: 20px !important;
            border-radius: 16px !important;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            transition: transform 0.2s ease;
        }
        
        [data-testid="stMetric"]:hover {
            transform: scale(1.02);
            border-color: var(--accent-blue);
        }

        /* Targets the inner label of metric blocks */
        [data-testid="stMetricLabel"] {
            color: var(--text-dim) !important;
            font-size: 14px !important;
            font-weight: 500 !important;
        }

        /* Targets the inner value of metric blocks */
        [data-testid="stMetricValue"] {
            color: var(--text-main) !important;
            font-size: 32px !important;
            font-weight: 700 !important;
        }

        /* Dataframe Table Headers */
        .stDataFrame thead tr th {
            background-color: var(--bg-secondary) !important;
            color: var(--text-dim) !important;
        }

        /* Alert boxes - softens the background color */
        .stAlert {
            background-color: rgba(30, 41, 59, 0.5) !important;
            border: 1px solid rgba(255,255,255,0.05) !important;
            color: var(--text-main) !important;
        }

        /* Custom divider - creates a fading line effect */
        hr {
            margin: 2em 0 !important;
            border: 0;
            height: 1px;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.1), transparent);
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("📊 SLA Audit Engine")
    st.markdown("*Advanced Margin Compliance Analytics*")

    # ==========================================
    # 1. Sidebar: SLA Master Section
    # ==========================================
    with st.sidebar:
        st.header("⚙️ Configuration")
        # Captures the uploaded SLA configurations rules
        uploaded_sla = st.file_uploader("Upload SLA Master (Excel)", type=['xlsx'])
        # Instantly process the SLA data into our dictionaries if uploaded
        sla_data = process_sla_upload(uploaded_sla) if uploaded_sla else None
        if sla_data:
            st.success(f"✅ SLA Master Loaded ({len(sla_data)} segments)")
        
        st.divider()
        
        # Tolerance config dictates the sensitivity of the pass/fail margin check
        st.subheader("📊 Audit Sensitivity")
        tolerance = st.slider("Variance Tolerance (%)", 0.0, 50.0, 10.0, step=1.0) / 100.0
        st.caption("Transactions within this % of target will be marked as 'Pass'.")

    # ==========================================
    # 2. Main Page: Sales Data Upload Section
    # ==========================================
    st.markdown("### 📥 Download Sales Data")
    st.info("Don't have the data yet? Download the Daily Sales CSV from this [Metabase link](https://metabase.korba365.com/question#eyJkYXRhc2V0X3F1ZXJ5Ijp7ImRhdGFiYXNlIjoxMzgsInR5cGUiOiJxdWVyeSIsInF1ZXJ5Ijp7InNvdXJjZS10YWJsZSI6MzA2OX19LCJkaXNwbGF5IjoidGFibGUiLCJ2aXN1YWxpemF0aW9uX3NldHRpbmdzIjp7fX0=).")
    # Upload button for the daily sales payload
    uploaded_sales = st.file_uploader("Upload Daily Sales (CSV)", type="csv")

    if uploaded_sales and sla_data:
        # Load and clean CSV headers by stripping edge whitespaces
        df_raw = pd.read_csv(uploaded_sales, low_memory=False)
        df_raw.columns = df_raw.columns.str.strip()
        
        st.divider()
        with st.container():
            st.subheader("🛠️ Column Mapping")
            st.info("Assign CSV columns to audit variables. Note: **Cor** uses 'Debit', **Self/Asst** uses 'Credit'. Best matches have been auto-selected.")
        
        def get_best_match(hints, columns):
            """
            Intelligently finds the index of the best matching uploaded column 
            based on a list of keyword hints to auto-select dropdown values.
            """
            import re
            # Priority 1: Check for exact word boundaries (e.g. 'cr' matches 'CR' but not 'Description')
            for index, col in enumerate(columns):
                if any(re.search(rf'\b{re.escape(hint.lower())}\b', col.lower()) for hint in hints):
                    return index
            # Priority 2: Fallback to simple substring match
            for index, col in enumerate(columns):
                if any(hint.lower() in col.lower() for hint in hints):
                    return index
            return 0
        
        # User-Interface for mapping CSV columns to the engine's internal variable names
        c1, c2, c3 = st.columns(3)
        
        # Segment & Category selection block
        with c1:
            seg_col = st.selectbox(
                "Biz Segment Column", df_raw.columns, 
                index=get_best_match(['biz seg', 'segment', 'seg'], df_raw.columns),
                help="Look for 'Biz Segment' or 'Segment'"
            )
            cat_col = st.selectbox(
                "Category Column", df_raw.columns, 
                index=get_best_match(['category', 'cat'], df_raw.columns),
                help="Look for 'Category'"
            )
            
        # Transaction variables block
        with c2:
            cre_col = st.selectbox(
                "Transaction Amt (Credit)", df_raw.columns, 
                index=get_best_match(['credit', 'cr'], df_raw.columns),
                help="Look for 'Credit Amt' or just 'Credit'"
            )
            
        # Outcomes and per-tab entity assignment block
        with c3:
            mar_col = st.selectbox(
                "Gr. Rev(GHC) Column", df_raw.columns, 
                index=get_best_match(['gross rev', 'gross margin', 'margin', 'rev'], df_raw.columns),
                help="Look for 'Gr. Rev(GHC)', 'Revenue', or 'Margin'"
            )
            
            # Build mapping dictionary that tells the engine exactly where to look for data
            map_dict = {'segment': seg_col, 'cat': cat_col, 'credit': cre_col, 'margin': mar_col}
            
            # Dynamically loop through the SLA configurations and ask for each sheet's specific Entity Name column mapping
            for tab in sla_data.keys():
                tab_hints = ['name', 'channel', 'client', 'agent', 'merchant']
                map_dict[tab] = st.selectbox(
                    f"Name Column for '{tab}'", df_raw.columns, 
                    key=f"map_{tab}",
                    index=get_best_match(tab_hints, df_raw.columns),
                    help=f"Look for '{tab} Name', 'Disbursement Channel Name', or 'Client Name'"
                )

        # ==========================================
        # 3. Audit Execution Block
        # ==========================================
        if st.button("🚀 Run Audit", type="primary"):
            # Executes the core calculation algorithm found in src/engine.py
            results = run_sla_audit(df_raw, sla_data, map_dict, tolerance=tolerance)
            
            if not results.empty:
                st.divider()
                
                # ==========================================
                # 4. Summary Metrics Display
                # ==========================================
                with st.container():
                    # Count up performance figures
                    pass_count = len(results[results['Status'] == 'Pass'])
                    fail_count = len(results[results['Status'] == 'Fail'])
                    total_count = len(results)
                    pass_rate = pass_count / total_count if total_count > 0 else 0
                    
                    # Render the stylized KPI metric cards row
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total Audits", f"{total_count:,}")
                    m2.metric("Passed ✅", f"{pass_count:,}")
                    # Shows negative delta if fail count exists
                    m3.metric("Failed ❌", f"{fail_count:,}", delta=f"{(fail_count/total_count):.1%}" if total_count > 0 else "0%", delta_color="inverse")
                    m4.metric("Success Rate", f"{pass_rate:.1%}")
                
                st.divider()
                
                # ==========================================
                # 5. Reporting Logic
                # ==========================================
                def style_status_text(row):
                    """
                    Returns a custom inline CSS styling map that colors the bold text 
                    inside the Status column based on if they failed or passed
                    """
                    status = row['Status']
                    color = ''
                    if status == 'Pass':
                        color = '#10b981'  # Vibrant Emerald for Pass
                    elif status == 'Fail':
                        color = '#f43f5e'  # Bold Rose/Crimson for Fail
                    elif status == 'No Target':
                        color = '#f59e0b'  # Amber for unspecified targets
                    
                    # Apply color ONLY to the 'Status' column text cell to prevent whole-row coloring
                    return [f'color: {color}; font-weight: bold' if col == 'Status' else '' for col in row.index]

                # Enforces explicit column order layout in the generated dataframe
                disp_cols = ['Biz seg', 'Cat', 'Name', 'Tier', 'Vol', 'Val(GHC)', 'Gr. Rev(GHC)', 'Margin %', 'SLA_Target', 'Var', 'Status']
                
                def render_styled_df(df):
                    """Formats the DataFrame string outputs for clean, localized currency displays"""
                    st.dataframe(
                        df[disp_cols].style.format({
                            'Val(GHC)': '{:,.2f}', 
                            'Gr. Rev(GHC)': '{:,.2f}', 
                            'Margin %': '{:.2%}', 
                            'SLA_Target': '{:.2%}', 
                            'Var': '{:+.2%}' # Forces + or - sign on variance
                        }).apply(style_status_text, axis=1), 
                        use_container_width=True
                    )

                # Interactive segment filtering using Streamlit Tabs
                tabs = st.tabs(["🌎 All", "🏢 Cor", "👤 Self", "🤝 Asst"])
                
                # Populate tabs with their pre-filtered dataset
                with tabs[0]: render_styled_df(results)
                with tabs[1]: render_styled_df(results[results['Biz seg'] == 'Cor'])
                with tabs[2]: render_styled_df(results[results['Biz seg'] == 'Self'])
                with tabs[3]: render_styled_df(results[results['Biz seg'] == 'Asst'])
                    
                # Handle Export download
                csv = results.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report", data=csv, file_name="SLA_Audit.csv", mime="text/csv")
            else:
                st.error("No data found for the mapped segments. Please check column mapping.")
    else:
        # Shown initially upon app mount
        st.warning("Please upload both the SLA Master (Excel) and Daily Sales (CSV) to begin.")

if __name__ == "__main__":
    main()