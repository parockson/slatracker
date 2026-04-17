import pandas as pd
import numpy as np

def process_sla_upload(uploaded_file):
    """
    Cleans and prepares the SLA Master Excel data.
    Ensures numeric columns are valid and tiers have default boundaries.
    """
    try:
        # Load all sheets from the Excel file
        sla_dict = pd.read_excel(uploaded_file, sheet_name=None)
        cleaned_dict = {}
        
        for sheet_name, df in sla_dict.items():
            df.columns = df.columns.str.strip()
            
            # Numeric columns that need cleaning (removing currency symbols/commas)
            num_cols = ['Min_Amt', 'Max_Amt', 'Target_Value', 'Limit_Value']
            for col in num_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            
            # Fill missing tier boundaries to ensure comparisons don't break
            if 'Min_Amt' in df.columns: df['Min_Amt'] = df['Min_Amt'].fillna(0)
            if 'Max_Amt' in df.columns: df['Max_Amt'] = df['Max_Amt'].fillna(99999999)
            
            # Normalize the 'Is_Percentage' flag to uppercase strings
            if 'Is_Percentage' in df.columns: 
                df['Is_Percentage'] = df['Is_Percentage'].astype(str).str.upper().str.strip()
                
            cleaned_dict[sheet_name.strip()] = df
        return cleaned_dict
    except Exception as e:
        print(f"Error in process_sla_upload: {e}")
        return None

def run_sla_audit(sales_df, sla_dict, user_map):
    """
    Core Audit Logic:
    1. Maps categories and segments to abbreviated names.
    2. Determines Tier for each transaction based on Debit (Cor) or Credit (Self/Asst).
    3. Groups results and calculates variance against the SLA target.
    """
    # Map raw CSV columns to internal processing keys
    internal_keys = {
        user_map['segment']: 'segment', 
        user_map['cat']: 'raw_cat', 
        user_map['debit']: 'debit_amt', 
        user_map['credit']: 'credit_amt',
        user_map['margin']: 'margin'
    }
    df = sales_df.rename(columns=internal_keys).copy()
    
    # Clean numeric sales data
    for col in ['debit_amt', 'credit_amt', 'margin']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)

    # Naming Dictionaries as requested
    cat_map = {
        'collection': 'col', 'disbursement': 'disb', 'disbursement 1': 'disb',
        'e-distribution': 'E-dis', 'remittance': 'Rem', 'disbursement 2': 'Rem',
        'airtime purchase': 'TopUp', 'data purchase': 'Data', 'utilities': 'UT',
        'funds transfer': 'FT', 'ticketing': 'TK'
    }
    seg_map = {'corporate': 'Cor', 'retail': 'Self', 'smb': 'Asst'}
    
    # Apply abbreviations
    df['Cat'] = df['raw_cat'].str.strip().str.lower().map(cat_map).fillna(df['raw_cat'])
    df['Biz seg'] = df['segment'].str.strip().str.lower().map(seg_map).fillna(df['segment'])

    final_report = []

    # Process each tab in the SLA Excel
    for original_tab_name, sla_table in sla_dict.items():
        # Identify rows in the CSV belonging to this segment
        seg_mask = df['segment'].astype(str).str.strip().str.lower() == original_tab_name.lower()
        seg_data = df[seg_mask].copy()
        if seg_data.empty: continue
            
        ent_col = user_map.get(original_tab_name)
        current_seg_abbr = seg_map.get(original_tab_name.lower(), original_tab_name)

        # Logic: Corporate audits use Debit, while Retail/SMB use Credit
        seg_data['active_val'] = seg_data['debit_amt'] if current_seg_abbr == 'Cor' else seg_data['credit_amt']

        def assign_tier_rules(row):
            """Determines which SLA bracket an individual transaction falls into."""
            raw_cat_val = str(row['raw_cat']).strip().lower()
            ent_val = str(row[ent_col]).strip().lower()
            amt = row['active_val']

            # Find name column (handles varying headers like 'Name' or 'Client')
            name_col_sla = next((c for c in sla_table.columns if c.lower().strip() in ['name', 'client', 'disbursement channel name']), None)
            
            rules = sla_table[
                (sla_table['Category'].astype(str).str.strip().str.lower() == raw_cat_val) & 
                (sla_table[name_col_sla].astype(str).str.strip().str.lower() == ent_val)
            ]

            # Match against amount-based tiers
            match = rules[(rules['Min_Amt'] <= amt) & (rules['Max_Amt'] >= amt)]
            
            if match.empty:
                return "No Tier", 0, "TRUE"
            
            rule = match.iloc[0]
            return f"T ({rule['Min_Amt']}-{rule['Max_Amt']})", rule['Target_Value'], rule.get('Is_Percentage', 'TRUE')

        # Tag every transaction with its tier
        tags = seg_data.apply(assign_tier_rules, axis=1)
        seg_data['Tier'], seg_data['T_Val'], seg_data['Is_P'] = [x[0] for x in tags], [x[1] for x in tags], [x[2] for x in tags]

        # Group data by the identified tiers
        grouped = seg_data.groupby(['Biz seg', 'Cat', ent_col, 'Tier', 'T_Val', 'Is_P']).agg({
            'active_val': 'sum', 
            'segment': 'count', # Using segment column to count rows
            'margin': 'sum'
        }).reset_index()

        grouped.columns = ['Biz seg', 'Cat', 'Name', 'Tier', 'T_Val', 'Is_P', 'Val(GHC)', 'Vol', 'Gr. Rev(GHC)']
        
        def calculate_performance(r):
            """Calculates if the group margin matches the SLA target within 10% tolerance."""
            if r['Tier'] == "No Tier": return 0, "No Target"
            
            t_val = float(r['T_Val'])
            is_pct = str(r['Is_P']).upper() == "TRUE"
            
            # Calculate Target Margin (Handle Flat Fee vs Percentage)
            target_pct = t_val if is_pct else (r['Vol'] * t_val) / r['Val(GHC)'] if r['Val(GHC)'] > 0 else 0
            
            actual_margin = r['Gr. Rev(GHC)'] / r['Val(GHC)'] if r['Val(GHC)'] > 0 else 0
            
            # 10% tolerance check
            diff = abs(actual_margin - target_pct)
            status = "Pass" if diff <= (abs(target_pct * 0.10) + 0.0001) else "Fail"
            
            return round(target_pct, 4), status

        # Final column calculations
        res = grouped.apply(calculate_performance, axis=1)
        grouped['SLA_Target'], grouped['Status'] = [x[0] for x in res], [x[1] for x in res]
        grouped['Margin %'] = (grouped['Gr. Rev(GHC)'] / grouped['Val(GHC)']).fillna(0)
        grouped['Var'] = grouped['Margin %'] - grouped['SLA_Target']
        
        final_report.append(grouped)

    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()