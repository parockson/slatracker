import pandas as pd

def get_date_range(sales_df):
    """Extracts the start and end date from the 'Time Created' column."""
    if 'Time Created' in sales_df.columns and not sales_df['Time Created'].empty:
        dates = pd.to_datetime(sales_df['Time Created'], errors='coerce')
        if not dates.dropna().empty:
            return dates.min().strftime('%Y-%m-%d'), dates.max().strftime('%Y-%m-%d')
    return "N/A", "N/A"

def run_sla_audit(sales_df, sla_dict):
    """Groups data and calculates measures with a 10% Relative Tolerance."""
    num_cols = ['Debit Amt', 'Gross Margin', 'Net Margin']
    for col in num_cols:
        if col in sales_df.columns:
            sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0).round(3)

    final_report = []
    for segment in ['Corporate', 'Retail', 'SMB']:
        seg_data = sales_df[sales_df['Biz Segment'] == segment]
        if seg_data.empty: continue
            
        lookup_col = 'Name' if segment == 'Corporate' else 'Disbursement Channel Name'
        group_cols = ['Category', lookup_col]

        pivot = seg_data.groupby(group_cols).agg({
            'Debit Amt': 'sum', 'Gross Margin': 'sum', 'Net Margin': 'sum'
        }).reset_index()

        pivot['Margin %'] = (pivot['Gross Margin'] / pivot['Debit Amt']).fillna(0).round(3)
        sla_table = sla_dict.get(segment)
        
        def check_status(row):
            if sla_table is None or sla_table.empty: return 0.000, "No SLA"
            
            match = sla_table[
                (sla_table['Category'].astype(str).str.strip() == str(row['Category']).strip()) & 
                (sla_table[lookup_col].astype(str).str.strip() == str(row[lookup_col]).strip())
            ]
            
            if match.empty: return 0.000, "No SLA"
            
            target = round(float(match.iloc[0]['Target']), 3)
            margin = row['Margin %']
            
            # RELATIVE TOLERANCE LOGIC (10% of Target)
            # Example: Target 0.048 * 0.10 = 0.0048 Allowed Deviation
            allowed_deviation = abs(target * 0.10)
            actual_deviation = abs(margin - target)
            
            status = "Pass" if actual_deviation <= allowed_deviation else "Fail"
            return target, status

        status_results = pivot.apply(check_status, axis=1)
        pivot['SLA_Target'] = [x[0] for x in status_results]
        pivot['Status'] = [x[1] for x in status_results]
        pivot['Variance'] = (pivot['Margin %'] - pivot['SLA_Target']).round(3)
        pivot['Biz Segment'] = segment
        final_report.append(pivot)

    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()

def get_failed_transactions(sales_df, audit_results):
    """Filters raw sales data to show only rows contributing to a 'Fail' status."""
    failed_summaries = audit_results[audit_results['Status'] == 'Fail'].copy()
    if failed_summaries.empty: return pd.DataFrame()

    failed_summaries['Match_Key'] = failed_summaries['Name'].fillna(failed_summaries['Disbursement Channel Name'])
    failed_keys = failed_summaries[['Biz Segment', 'Category', 'Match_Key']]
    
    temp_raw = sales_df.copy()
    temp_raw['Match_Key'] = temp_raw['Name'].fillna(temp_raw['Disbursement Channel Name'])
    
    return temp_raw.merge(failed_keys, on=['Biz Segment', 'Category', 'Match_Key'], how='inner').drop(columns=['Match_Key'])