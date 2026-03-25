"""
Audit Engine Module - SLA Price Tracker

This module contains the core logic for calculating performance metrics and 
auditing sales data against SLA targets. It includes logic for date extraction, 
summary generation, and the relative tolerance-based audit calculation.
"""

import pandas as pd

def get_date_range(sales_df):
    """
    Extracts the minimum and maximum dates from the 'Time Created' column.

    Args:
        sales_df (pd.DataFrame): The sales data containing transaction timestamps.

    Returns:
        tuple: (start_date_str, end_date_str) formatted as YYYY-MM-DD.
    """
    if 'Time Created' in sales_df.columns and not sales_df['Time Created'].empty:
        # Convert to datetime with error handling for inconsistent formats
        dates = pd.to_datetime(sales_df['Time Created'], errors='coerce')
        if not dates.dropna().empty:
            return dates.min().strftime('%Y-%m-%d'), dates.max().strftime('%Y-%m-%d')
    return "N/A", "N/A"

def get_performance_summary(audit_results):
    """
    Aggregates audit results into a high-level performance summary by business segment.

    Args:
        audit_results (pd.DataFrame): The output from run_sla_audit.

    Returns:
        pd.DataFrame: A summary table with totals and global margin percentages.
    """
    if audit_results is None or audit_results.empty:
        return pd.DataFrame()
    
    # Group by segment and sum key financial metrics
    summary = audit_results.groupby('Biz Segment').agg({
        'Debit Amt': 'sum',
        'Gross Margin': 'sum'
    }).reset_index()
    
    # Calculate weighted average margin percentage for each segment
    summary['Margin %'] = (summary['Gross Margin'] / summary['Debit Amt']).fillna(0).round(3)
    
    # Calculate grand totals
    total_debit = summary['Debit Amt'].sum()
    total_margin = summary['Gross Margin'].sum()
    
    total_row = pd.DataFrame({
        'Biz Segment': ['GRAND TOTAL'],
        'Debit Amt': [total_debit],
        'Gross Margin': [total_margin],
        'Margin %': [(total_margin / total_debit if total_debit > 0 else 0)]
    })
    
    return pd.concat([summary, total_row], ignore_index=True)

def run_sla_audit(sales_df, sla_dict):
    """
    Main audit function. Groups transactions and compares actual margins to SLA targets.
    
    Logic:
    1. Group data by Category and Name/Disbursement Channel.
    2. Lookup the corresponding SLA target for that pair in the provided segment.
    3. Apply a 10% Relative Tolerance:
       Pass if: |Actual Margin - Target| <= 10% of Target.
       Else: Fail.
    4. If no target exists in config, status is 'No Target'.

    Args:
        sales_df (pd.DataFrame): The raw sales transaction data.
        sla_dict (dict): Dictionary of SLA target DataFrames by segment.

    Returns:
        pd.DataFrame: A pivoted report containing grouped metrics and audit status.
    """
    # Ensure numerical columns are correctly typed and rounded
    num_cols = ['Debit Amt', 'Gross Margin', 'Net Margin']
    for col in num_cols:
        if col in sales_df.columns:
            sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0).round(3)

    final_report = []
    # Process each segment independently
    for segment in ['Corporate', 'Retail', 'SMB']:
        seg_data = sales_df[sales_df['Biz Segment'] == segment]
        if seg_data.empty: continue
            
        # Determine the key identifier column for this segment
        lookup_col = 'Name' if segment == 'Corporate' else 'Disbursement Channel Name'
        
        # Pivot the raw data to calculate aggregate margins per category/entity
        pivot = seg_data.groupby(['Category', lookup_col]).agg({
            'Debit Amt': 'sum', 'Gross Margin': 'sum', 'Net Margin': 'sum'
        }).reset_index()

        pivot['Margin %'] = (pivot['Gross Margin'] / pivot['Debit Amt']).fillna(0).round(3)
        sla_table = sla_dict.get(segment)
        
        def check_status(row):
            """Internal helper to match a row against the SLA table and calculate status."""
            if sla_table is None or sla_table.empty: return None, "No Target"
            
            # Find the specific target for this Category + Entity
            match = sla_table[
                (sla_table['Category'].astype(str).str.strip() == str(row['Category']).strip()) & 
                (sla_table[lookup_col].astype(str).str.strip() == str(row[lookup_col]).strip())
            ]
            
            if match.empty: return None, "No Target"
            
            target = round(float(match.iloc[0]['Target']), 3)
            # 10% Relative Tolerance Logic
            allowed_deviation = abs(target * 0.10)
            actual_diff = abs(row['Margin %'] - target)
            
            # Status check with a small epsilon (0.0001) for floating point safety
            status = "Pass" if actual_diff <= (allowed_deviation + 0.0001) else "Fail"
            return target, status

        # Apply the status check to the pivoted data
        res = pivot.apply(check_status, axis=1)
        pivot['SLA_Target'] = [x[0] for x in res]
        pivot['Status'] = [x[1] for x in res]
        # Calculate variance from target
        pivot['Variance'] = pivot.apply(lambda r: round(r['Margin %'] - r['SLA_Target'], 3) if r['SLA_Target'] is not None else None, axis=1)
        pivot['Biz Segment'] = segment
        final_report.append(pivot)

    # Combine results from all segments into a single report
    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()

def get_filtered_raw(sales_df, audit_results, status_filter):
    """
    Retrieves original raw transactions associated with a specific audit status.

    Args:
        sales_df (pd.DataFrame): The original raw sales data.
        audit_results (pd.DataFrame): The pivoted audit report.
        status_filter (str): One of 'Pass', 'Fail', or 'No Target'.

    Returns:
        pd.DataFrame: A subset of transactions matching the filter.
    """
    # Identify the unique combinations (Category + Entity) that match the status
    target_summary = audit_results[audit_results['Status'] == status_filter].copy()
    if target_summary.empty: return pd.DataFrame()
    
    # Create a composite key for merging back to raw data
    target_summary['M_Key'] = target_summary['Name'].fillna(target_summary['Disbursement Channel Name'])
    temp = sales_df.copy()
    temp['M_Key'] = temp['Name'].fillna(temp['Disbursement Channel Name'])
    
    # Join raw data with the target list to filter transactions
    merged = temp.merge(target_summary[['Biz Segment', 'Category', 'M_Key']], 
                        on=['Biz Segment', 'Category', 'M_Key'], 
                        how='inner')
    
    return merged.drop(columns=['M_Key'])