"""
Audit Engine Module - SLA Price Tracker

Core logic for:
1. Date extraction for reporting.
2. Performance summary aggregation.
3. 10% Relative Tolerance Audit (Pass/Fail/No Target).
"""

import pandas as pd

def get_date_range(sales_df):
    """Extracts start and end dates formatted as YYYY-MM-DD."""
    if 'Time Created' in sales_df.columns and not sales_df['Time Created'].empty:
        dates = pd.to_datetime(sales_df['Time Created'], errors='coerce')
        if not dates.dropna().empty:
            return dates.min().strftime('%Y-%m-%d'), dates.max().strftime('%Y-%m-%d')
    return "N/A", "N/A"

def get_performance_summary(audit_results):
    """Aggregates audit results into a segment-level summary."""
    if audit_results is None or audit_results.empty:
        return pd.DataFrame()
    
    summary = audit_results.groupby('Biz Segment').agg({
        'Debit Amt': 'sum',
        'Gross Margin': 'sum'
    }).reset_index()
    
    summary['Margin %'] = (summary['Gross Margin'] / summary['Debit Amt']).fillna(0).round(3)
    
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
    Groups data and applies 10% Relative Tolerance Audit.
    Logic: |Actual - Target| <= (Target * 0.10)
    """
    # Standardize numerical types
    num_cols = ['Debit Amt', 'Gross Margin', 'Net Margin']
    for col in num_cols:
        if col in sales_df.columns:
            sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0).round(3)

    final_report = []
    # Standardize Biz Segment values in the dataframe for robust matching
    sales_df['Biz Segment'] = sales_df['Biz Segment'].astype(str).str.strip()

    for segment in ['Corporate', 'Retail', 'SMB']:
        # Case-insensitive segment matching
        seg_data = sales_df[sales_df['Biz Segment'].str.lower() == segment.lower()]
        if seg_data.empty: continue
            
        lookup_col = 'Name' if segment == 'Corporate' else 'Disbursement Channel Name'
        
        # Aggregate data by Category and the specific Entity Column
        pivot = seg_data.groupby(['Category', lookup_col]).agg({
            'Debit Amt': 'sum', 'Gross Margin': 'sum', 'Net Margin': 'sum'
        }).reset_index()

        pivot['Margin %'] = (pivot['Gross Margin'] / pivot['Debit Amt']).fillna(0).round(3)
        sla_table = sla_dict.get(segment)
        
        def check_status(row):
            if sla_table is None or sla_table.empty: return None, "No Target"
            
            # Robust matching: Strip whitespace and match strings
            cat_val = str(row['Category']).strip().lower()
            ent_val = str(row[lookup_col]).strip().lower()
            
            match = sla_table[
                (sla_table['Category'].astype(str).str.strip().str.lower() == cat_val) & 
                (sla_table[lookup_col].astype(str).str.strip().str.lower() == ent_val)
            ]
            
            if match.empty: return None, "No Target"
            
            target = round(float(match.iloc[0]['Target']), 3)
            # 10% Relative Tolerance Logic
            allowed_deviation = abs(target * 0.10)
            actual_diff = abs(row['Margin %'] - target)
            
            # Use 0.0001 epsilon to handle floating point precision issues
            status = "Pass" if actual_diff <= (allowed_deviation + 0.0001) else "Fail"
            return target, status

        res = pivot.apply(check_status, axis=1)
        pivot['SLA_Target'] = [x[0] for x in res]
        pivot['Status'] = [x[1] for x in res]
        pivot['Variance'] = pivot.apply(lambda r: round(r['Margin %'] - r['SLA_Target'], 3) 
                                        if r['SLA_Target'] is not None else None, axis=1)
        pivot['Biz Segment'] = segment
        final_report.append(pivot)

    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()

def get_filtered_raw(sales_df, audit_results, status_filter):
    """Filters raw CSV rows matching a specific status (e.g., 'Fail')."""
    target_summary = audit_results[audit_results['Status'] == status_filter].copy()
    if target_summary.empty: return pd.DataFrame()
    
    # Create a helper key for filtering
    target_summary['M_Key'] = target_summary['Name'].fillna(target_summary['Disbursement Channel Name']).astype(str).str.strip().str.lower()
    
    temp = sales_df.copy()
    temp['M_Key'] = temp['Name'].fillna(temp['Disbursement Channel Name']).astype(str).str.strip().str.lower()
    
    # Inner join to keep only transactions belonging to the filtered status
    merged = temp.merge(target_summary[['Biz Segment', 'Category', 'M_Key']], 
                        on=['Biz Segment', 'Category', 'M_Key'], 
                        how='inner')
    
    return merged.drop(columns=['M_Key'])