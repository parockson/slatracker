"""
Data Loader Module - SLA Price Tracker

This module handles the extraction and cleaning of data from the Excel config
and the uploaded Sales CSV. It ensures all strings are stripped of whitespace
to maintain data integrity during the audit.
"""

import pandas as pd
import streamlit as st
import os

@st.cache_data(ttl=3600)
def load_all_slas(file_path):
    """Loads SLA targets from Corporate, Retail, and SMB sheets."""
    if not os.path.exists(file_path):
        return None
    try:
        xls = pd.ExcelFile(file_path, engine='openpyxl')
        sla_dict = {}
        for sheet in ["Corporate", "Retail", "SMB"]:
            if sheet in xls.sheet_names:
                df = pd.read_excel(xls, sheet)
                # Clean column headers
                df.columns = df.columns.astype(str).str.strip()
                # Clean string data in all object columns
                for col in df.select_dtypes(include=['object']).columns:
                    df[col] = df[col].astype(str).str.strip()
                sla_dict[sheet] = df
        return sla_dict
    except Exception as e:
        st.error(f"Error loading Excel: {e}")
        return None

def process_sales_data(file):
    """Reads and cleans the uploaded Sales CSV file."""
    try:
        # Use low_memory=False to handle mixed types in large files
        df = pd.read_csv(file, low_memory=False)
        # Clean column headers
        df.columns = df.columns.astype(str).str.strip()
        # Clean string data in all object columns
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error processing CSV: {e}")
        return None