import pandas as pd
import numpy as np

def process_sla_upload(uploaded_file):
    """
    Cleans and prepares the SLA Master Excel data.
    Ensures numeric columns are valid and tiers have default boundaries.
    """
    try:
        sla_dict = pd.read_excel(uploaded_file, sheet_name=None)
        cleaned_dict = {}
        
        for sheet_name, df in sla_dict.items():
            df.columns = df.columns.str.strip()
            
            # Numeric columns cleaning
            num_cols = ['Min_Amt', 'Max_Amt', 'Target_Value', 'Limit_Value']
            for col in num_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            
            # Default boundaries
            if 'Min_Amt' in df.columns: df['Min_Amt'] = df['Min_Amt'].fillna(0)
            if 'Max_Amt' in df.columns: df['Max_Amt'] = df['Max_Amt'].fillna(99999999)
            
            if 'Is_Percentage' in df.columns: 
                df['Is_Percentage'] = df['Is_Percentage'].astype(str).str.upper().str.strip()
                
            # Standardize string columns for matching
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
                
            cleaned_dict[sheet_name.strip()] = df
        return cleaned_dict
    except Exception as e:
        print(f"Error in process_sla_upload: {e}")
        return None

def run_sla_audit(sales_df, sla_dict, user_map, tolerance=0.10):
    """
    Performs row-level analysis to handle tiered caps (e.g., 1% max GHS 25).
    """
    # 1. Standardize Sales Data
    internal_keys = {
        user_map['segment']: 'segment', 
        user_map['cat']: 'raw_cat', 
        user_map['debit']: 'debit_amt', 
        user_map['credit']: 'credit_amt',
        user_map['margin']: 'margin'
    }
    df = sales_df.rename(columns=internal_keys).copy()
    
    for col in ['debit_amt', 'credit_amt', 'margin']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)

    # Mapping logic
    cat_map = {
        'collection': 'col', 'disbursement': 'disb', 'disbursement 1': 'disb',
        'e-distribution': 'E-dis', 'remittance': 'Rem', 'disbursement 2': 'Rem',
        'airtime purchase': 'TopUp', 'data purchase': 'Data', 'utilities': 'UT',
        'funds transfer': 'FT', 'ticketing': 'TK'
    }
    seg_map = {'corporate': 'Cor', 'retail': 'Self', 'smb': 'Asst'}
    
    df['segment_low'] = df['segment'].astype(str).str.strip().str.lower()
    df['raw_cat_low'] = df['raw_cat'].astype(str).str.strip().str.lower()
    df['Cat'] = df['raw_cat_low'].map(cat_map).fillna(df['raw_cat'])
    df['Biz seg'] = df['segment_low'].map(seg_map).fillna(df['segment'])

    final_report = []

    # 2. Process each Segment Tab
    for original_tab_name, sla_table in sla_dict.items():
        tab_name_low = original_tab_name.lower()
        seg_mask = df['segment_low'] == tab_name_low
        seg_data = df[seg_mask].copy()
        if seg_data.empty: continue
            
        ent_col_raw = user_map.get(original_tab_name)
        seg_data['__original_entity_name__'] = sales_df.loc[seg_data.index, ent_col_raw]
        seg_data['ent_low'] = seg_data['__original_entity_name__'].astype(str).str.strip().str.lower()
        
        current_seg_abbr = seg_map.get(tab_name_low, original_tab_name)
        seg_data['active_val'] = seg_data['debit_amt'] if current_seg_abbr == 'Cor' else seg_data['credit_amt']
        seg_data['temp_id'] = range(len(seg_data))

        name_col_sla = next((c for c in sla_table.columns if c.lower().strip() in ['name', 'client', 'disbursement channel name']), None)
        if not name_col_sla: continue

        # Merge with SLA
        merged = seg_data.merge(
            sla_table, 
            left_on=['raw_cat_low', 'ent_low'], 
            right_on=['Category', name_col_sla], 
            how='left'
        )

        # Tier Filter
        tier_match_mask = (merged['active_val'] >= merged['Min_Amt']) & (merged['active_val'] <= merged['Max_Amt'])
        matches = merged[tier_match_mask].copy()
        
        # Handle unmatched rows
        matched_temp_ids = matches['temp_id'].unique()
        no_matches = seg_data[~seg_data['temp_id'].isin(matched_temp_ids)].copy()
        
        if not no_matches.empty:
            no_matches['Tier'] = "No Tier"
            no_matches['Target_Value'], no_matches['Is_Percentage'], no_matches['Limit_Value'] = 0, "TRUE", 99999999
            no_matches['Min_Amt'], no_matches['Max_Amt'] = 0, 0
            processed_data = pd.concat([matches, no_matches], ignore_index=True)
        else:
            processed_data = matches

        # Formatted Tier Label (Safe from IntCastingNaNError)
        processed_data['Tier'] = np.where(
            processed_data['Tier'] == "No Tier", 
            "No Tier", 
            "T (" + 
            processed_data['Min_Amt'].fillna(0).astype(int).astype(str) + 
            "-" + 
            processed_data['Max_Amt'].fillna(0).astype(int).astype(str) + 
            ")"
        )

        # --- ROW-LEVEL AUDIT (The Cap Engine) ---
        def calculate_expected_fee(row):
            if row['Tier'] == "No Tier": return 0
            
            val = row['active_val']
            target = float(row.get('Target_Value', 0))
            is_pct = str(row.get('Is_Percentage', 'TRUE')).upper() == "TRUE"
            cap = row.get('Limit_Value', 99999999) 
            
            if pd.isna(cap) or cap == 0: cap = 99999999
            
            if is_pct:
                # Actual logic check: If calculated % exceeds cap, use cap
                return min(val * target, cap)
            else:
                return target

        processed_data['expected_fee_ghc'] = processed_data.apply(calculate_expected_fee, axis=1)

        # 3. Final Grouping & Aggregation
        grouped = processed_data.groupby(['Biz seg', 'Cat', '__original_entity_name__', 'Tier']).agg({
            'active_val': 'sum',      
            'temp_id': 'count',       
            'margin': 'sum',          
            'expected_fee_ghc': 'sum' 
        }).reset_index()

        grouped.rename(columns={
            'active_val': 'Val(GHC)', 
            'temp_id': 'Vol', 
            'margin': 'Gr. Rev(GHC)', 
            '__original_entity_name__': 'Name'
        }, inplace=True)
        
        # Effective Percentages
        grouped['SLA_Target'] = (grouped['expected_fee_ghc'] / grouped['Val(GHC)']).fillna(0)
        grouped['Margin %'] = (grouped['Gr. Rev(GHC)'] / grouped['Val(GHC)']).fillna(0)
        grouped['Var'] = grouped['Margin %'] - grouped['SLA_Target']
        
        # Status assignment
        diff = (grouped['Margin %'] - grouped['SLA_Target']).abs()
        status_pass = diff <= ( (grouped['SLA_Target'].abs() * tolerance) + 0.0001 )
        
        grouped['Status'] = np.where(grouped['Tier'] == "No Tier", "No Target", np.where(status_pass, "Pass", "Fail"))
        grouped['SLA_Target'] = grouped['SLA_Target'].round(4)
        
        final_report.append(grouped)

    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()