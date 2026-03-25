import pandas as pd
import streamlit as st

@st.cache_data
def load_all_slas(file_path):
    """Loads Corporate, Retail, and SMB sheets from Excel."""
    try:
        xls = pd.ExcelFile(file_path)
        available = xls.sheet_names
        sla_dict = {}
        
        for sheet in ["Corporate", "Retail", "SMB"]:
            if sheet in available:
                df = pd.read_excel(xls, sheet)
                df.columns = df.columns.str.strip()
                sla_dict[sheet] = df
            else:
                st.warning(f"Sheet '{sheet}' not found in Excel.")
                sla_dict[sheet] = pd.DataFrame()
        return sla_dict
    except Exception as e:
        st.error(f"Error loading SLA file: {e}")
        return None

def process_sales_data(uploaded_file):
    """Reads the user-uploaded sales CSV and cleans headers."""
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            return None
    return None