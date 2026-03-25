"""
Data Loader Module - SLA Price Tracker

This module provides functions to load and preprocess data from Excel and CSV files.
It handles standardization of column names and string content to ensure consistency 
during the audit process.
"""

import pandas as pd
import streamlit as st
import os

@st.cache_data(ttl=3600)
def load_all_slas(file_path):
    """
    Loads SLA targets from multiple sheets in an Excel configuration file.
    
    Expected sheets: "Corporate", "Retail", "SMB".
    Each sheet should contain 'Category', 'Target', and segment-specific 
    identifier columns (e.g., 'Name' for Corporate).

    Args:
        file_path (str): The absolute path to the Excel file.

    Returns:
        dict: A dictionary where keys are segment names and values are DataFrames,
              or None if the file is missing or an error occurs.
    """
    if not os.path.exists(file_path):
        return None
    try:
        xls = pd.ExcelFile(file_path, engine='openpyxl')
        sla_dict = {}
        for sheet in ["Corporate", "Retail", "SMB"]:
            if sheet in xls.sheet_names:
                df = pd.read_excel(xls, sheet)
                # Standardize column names and string content
                df.columns = df.columns.astype(str).str.strip()
                for col in df.select_dtypes(include=['object']).columns:
                    df[col] = df[col].astype(str).str.strip()
                sla_dict[sheet] = df
        return sla_dict
    except Exception as e:
        st.error(f"Error loading Excel: {e}")
        return None

def process_sales_data(file):
    """
    Reads and cleans the uploaded Sales CSV file.
    
    Performs basic cleaning such as stripping whitespace from column names 
    and string values to prevent matching issues.

    Args:
        file (file-like object): The uploaded CSV file from Streamlit.

    Returns:
        pd.DataFrame: A cleaned DataFrame, or None if an error occurs.
    """
    try:
        df = pd.read_csv(file)
        # Standardize column names and string content
        df.columns = df.columns.astype(str).str.strip()
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error processing CSV: {e}")
        return None