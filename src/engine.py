import pandas as pd

def process_sla_upload(uploaded_file):
    """Converts uploaded SLA Excel into a dictionary of DataFrames."""
    try:
        sla_dict = pd.read_excel(uploaded_file, sheet_name=None)
        cleaned_dict = {}
        for sheet_name, df in sla_dict.items():
            df.columns = df.columns.str.strip()
            if 'Category' in df.columns and 'Target' in df.columns:
                cleaned_dict[sheet_name] = df
        return cleaned_dict
    except Exception:
        return None

def get_date_range(sales_df):
    """Extracts start and end dates from 'Time Created'."""
    if 'Time Created' in sales_df.columns and not sales_df['Time Created'].empty:
        dates = pd.to_datetime(sales_df['Time Created'], errors='coerce')
        if not dates.dropna().empty:
            return dates.min().strftime('%Y-%m-%d'), dates.max().strftime('%Y-%m-%d')
    return "N/A", "N/A"

def get_performance_summary(audit_results):
    """Aggregates results for the dashboard metrics."""
    if audit_results is None or audit_results.empty:
        return pd.DataFrame()
    summary = audit_results.groupby('Biz Segment').agg({
        'Debit Amt': 'sum', 'Gross Margin': 'sum'
    }).reset_index()
    summary['Margin %'] = (summary['Gross Margin'] / summary['Debit Amt']).fillna(0)
    
    total_debit = summary['Debit Amt'].sum()
    total_margin = summary['Gross Margin'].sum()
    total_row = pd.DataFrame({
        'Biz Segment': ['GRAND TOTAL'],
        'Debit Amt': [total_debit],
        'Gross Margin': [total_margin],
        'Margin %': [(total_margin / total_debit if total_debit > 0 else 0)]
    })
    return pd.concat([summary, total_row], ignore_index=True)

def run_sla_audit(sales_df, sla_dict, col_mapping=None):
    """Core Audit with 10% Relative Tolerance and Mapping."""
    num_cols = ['Debit Amt', 'Gross Margin', 'Net Margin']
    for col in num_cols:
        if col in sales_df.columns:
            sales_df[col] = pd.to_numeric(sales_df[col], errors='coerce').fillna(0)

    final_report = []
    sales_df['Biz Segment'] = sales_df['Biz Segment'].astype(str).str.strip()

    for segment in ['Corporate', 'Retail', 'SMB']:
        seg_data = sales_df[sales_df['Biz Segment'].str.lower() == segment.lower()].copy()
        if seg_data.empty: continue
            
        lookup_col = col_mapping.get(segment) if col_mapping else ('Name' if segment == 'Corporate' else 'Disbursement Channel Name')
        if lookup_col not in seg_data.columns: continue

        pivot = seg_data.groupby(['Category', lookup_col]).agg({
            'Debit Amt': 'sum', 'Gross Margin': 'sum', 'Net Margin': 'sum'
        }).reset_index()

        pivot['Margin %'] = (pivot['Gross Margin'] / pivot['Debit Amt']).fillna(0)
        sla_table = sla_dict.get(segment)
        
        def check_status(row):
            if sla_table is None or sla_table.empty: return None, "No Target"
            cat_val = str(row['Category']).strip().lower()
            ent_val = str(row[lookup_col]).strip().lower()
            
            # Match logic
            target_ent_col = lookup_col if lookup_col in sla_table.columns else sla_table.columns[1]
            match = sla_table[
                (sla_table['Category'].astype(str).str.strip().str.lower() == cat_val) & 
                (sla_table[target_ent_col].astype(str).str.strip().str.lower() == ent_val)
            ]
            if match.empty: return None, "No Target"
            
            target = float(match.iloc[0]['Target'])
            allowed_deviation = abs(target * 0.10)
            actual_diff = abs(row['Margin %'] - target)
            status = "Pass" if actual_diff <= (allowed_deviation + 0.0001) else "Fail"
            return target, status

        res = pivot.apply(check_status, axis=1)
        pivot['SLA_Target'] = [x[0] for x in res]
        pivot['Status'] = [x[1] for x in res]
        pivot['Variance'] = pivot.apply(lambda r: (r['Margin %'] - r['SLA_Target']) if r['SLA_Target'] is not None else None, axis=1)
        pivot['Biz Segment'] = segment
        pivot = pivot.rename(columns={lookup_col: 'Entity_Name'})
        final_report.append(pivot)

    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()

def get_filtered_raw(sales_df, audit_results, status_filter, col_mapping=None):
    """Filters raw CSV rows for Pass/Fail/No Target."""
    target_summary = audit_results[audit_results['Status'] == status_filter].copy()
    if target_summary.empty: return pd.DataFrame()
    target_summary['M_Key'] = target_summary['Entity_Name'].astype(str).str.strip().str.lower()
    
    temp = sales_df.copy()
    def create_raw_key(row):
        seg = row['Biz Segment']
        col = col_mapping.get(seg) if col_mapping else ('Name' if seg == 'Corporate' else 'Disbursement Channel Name')
        return str(row.get(col, "")).strip().lower()

    temp['M_Key'] = temp.apply(create_raw_key, axis=1)
    merged = temp.merge(target_summary[['Biz Segment', 'Category', 'M_Key']], on=['Biz Segment', 'Category', 'M_Key'], how='inner')
    return merged.drop(columns=['M_Key'])