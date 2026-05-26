import pandas as pd
import numpy as np

def process_sla_upload(uploaded_file):
    """
    Cleans and prepares the SLA Master Excel data.
    Handles dashes in Limit_Value and standardizes headers.
    """
    try:
        sla_dict = pd.read_excel(uploaded_file, sheet_name=None)
        cleaned_dict = {}
        
        for sheet_name, df in sla_dict.items():
            df.columns = df.columns.str.strip()
            
            # Numeric cleaning (Handles currency, commas, and dashes)
            num_cols = ['Min_Amt', 'Max_Amt', 'Target_Value', 'Limit_Value']
            for col in num_cols:
                if col in df.columns:
                    # Replace dash with a very high number (no limit) or NaN for cleaning
                    df[col] = df[col].astype(str).replace('-', '99999999').replace('nan', '0')
                    df[col] = pd.to_numeric(df[col].str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            
            # Fill missing tier boundaries
            if 'Min_Amt' in df.columns: df['Min_Amt'] = df['Min_Amt'].fillna(0)
            if 'Max_Amt' in df.columns: df['Max_Amt'] = df['Max_Amt'].fillna(999999)
            
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
    Core Audit Engine:
    Correctly matches SMB/Retail 'Disbursement Channel Name' and Corporate 'Name'.
    Switches to Credit_Amt for SMB and Retail segments.
    """
    # 1. Standardize Sales Data
    internal_keys = {
        user_map['segment']: 'segment', 
        user_map['cat']: 'raw_cat', 
        user_map['credit']: 'credit_amt',
        user_map['margin']: 'margin'
    }
    if 'dest_fund' in user_map:
        internal_keys[user_map['dest_fund']] = 'dest_fund'
        
    df = sales_df.rename(columns=internal_keys).copy()
    
    if 'dest_fund' in df.columns:
        df['dest_fund_low'] = df['dest_fund'].astype(str).str.strip().str.lower()
    else:
        df['dest_fund'] = ""
        df['dest_fund_low'] = ""
    
    for col in ['credit_amt', 'margin']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)

    # Category and Segment Mappings
    cat_map = {
        'collection': 'col', 'disbursement': 'disb', 'airtime purchase': 'topup',
        'e-distribution': 'e-dis', 'remittance': 'rem', 'utilities': 'ut'
    }
    seg_map = {'corporate': 'Cor', 'retail': 'Self', 'smb': 'Asst'}
    
    df['segment_low'] = df['segment'].astype(str).str.strip().str.lower()
    df['raw_cat_low'] = df['raw_cat'].astype(str).str.strip().str.lower()
    df['Cat'] = df['raw_cat_low'].map(cat_map).fillna(df['raw_cat'])
    df['Biz seg'] = df['segment_low'].map(seg_map).fillna(df['segment'])

    final_report = []

    # 2. Process each Sheet (Corporate, Retail, SMB)
    for original_tab_name, sla_table in sla_dict.items():
        tab_name_low = original_tab_name.lower().strip()
        
        # Filter sales data to the current segment
        seg_mask = df['segment_low'].str.contains(tab_name_low) | df['segment_low'].apply(lambda x: x in tab_name_low)
        seg_data = df[seg_mask].copy()
        
        if seg_data.empty: continue
            
        # Get entity name from Sales file (Dynamic mapping)
        ent_col_raw = user_map.get(original_tab_name)
        if ent_col_raw and ent_col_raw in sales_df.columns:
            seg_data['Name_Sales'] = sales_df.loc[seg_data.index, ent_col_raw]
        else:
            seg_data['Name_Sales'] = sales_df.iloc[seg_data.index, 0] # Fallback to first column

        # Extract Destination Of Fund (original unmodified name)
        seg_data['Destination Of Fund'] = seg_data['dest_fund'].astype(str).str.strip()
        
        # Match using Name_Sales (lowercased)
        seg_data['name_low'] = seg_data['Name_Sales'].astype(str).str.strip().str.lower()
        
        # LOGIC: All segments now use Credit Amt
        seg_data['active_val'] = seg_data['credit_amt']
        seg_data['temp_id'] = range(len(seg_data))

        # Identify 'Name' or 'Disbursement Channel Name' in SLA sheet
        name_col_sla = next((c for c in sla_table.columns if c.lower().strip() in 
                            ['name', 'client', 'disbursement channel name', 'partner']), None)
        
        if not name_col_sla:
            name_col_sla = sla_table.columns[0] # Extreme Fallback

        # Identify if 'Destination Of Fund' is present in the SLA sheet
        dest_col_sla = next((c for c in sla_table.columns if c.lower().strip() == 'destination of fund'), None)

        if dest_col_sla:
            # Join Sales with SLA including Destination Of Fund
            merged = seg_data.merge(
                sla_table, 
                left_on=['raw_cat_low', 'name_low', 'dest_fund_low'], 
                right_on=['Category', name_col_sla, dest_col_sla], 
                how='left',
                suffixes=('', '_sla')
            )
        else:
            # Fallback join without Destination Of Fund
            merged = seg_data.merge(
                sla_table, 
                left_on=['raw_cat_low', 'name_low'], 
                right_on=['Category', name_col_sla], 
                how='left',
                suffixes=('', '_sla')
            )

        # Tier Filter Logic
        tier_match_mask = (merged['active_val'] >= merged['Min_Amt']) & (merged['active_val'] <= merged['Max_Amt'])
        matches = merged[tier_match_mask].copy()
        
        matched_ids = matches['temp_id'].unique()
        no_matches = seg_data[~seg_data['temp_id'].isin(matched_ids)].copy()
        
        if not no_matches.empty:
            no_matches['Tier'] = "No Tier"
            for c in ['Target_Value', 'Limit_Value', 'Min_Amt', 'Max_Amt']: no_matches[c] = 0
            no_matches['Is_Percentage'] = "TRUE"
            processed_data = pd.concat([matches, no_matches], ignore_index=True)
        else:
            processed_data = matches.copy()

        # Handle column bootstrapping
        required = ['Tier', 'Min_Amt', 'Max_Amt', 'Target_Value', 'Is_Percentage', 'Limit_Value']
        for col in required:
            if col not in processed_data.columns:
                processed_data[col] = 0 if 'Amt' in col or 'Value' in col else "TRUE"

        # Tier String Formatting
        processed_data['Tier'] = np.where(
            processed_data['Tier'] == "No Tier", "No Tier", 
            "T (" + processed_data['Min_Amt'].fillna(0).astype(int).astype(str) + "-" + 
            processed_data['Max_Amt'].fillna(0).astype(int).astype(str) + ")"
        )

        # --- Row-Level Audit Calculation ---
        def calculate_expected_fee(row):
            if row['Tier'] == "No Tier": return 0
            val = row['active_val']
            target = float(row.get('Target_Value', 0))
            is_pct = str(row.get('Is_Percentage', 'TRUE')).upper() == "TRUE"
            cap = row.get('Limit_Value', 99999999)
            
            # Treat 0 or null caps as effectively infinite
            if pd.isna(cap) or cap == 0: cap = 99999999
            
            return min(val * target, cap) if is_pct else target

        processed_data['expected_fee_ghc'] = processed_data.apply(calculate_expected_fee, axis=1)

        # 3. Final Aggregation
        grouped = processed_data.groupby(['Biz seg', 'Cat', 'Name_Sales', 'Destination Of Fund', 'Tier']).agg({
            'active_val': 'sum', 'temp_id': 'count', 'margin': 'sum', 'expected_fee_ghc': 'sum'
        }).reset_index()

        grouped.rename(columns={
            'active_val': 'Val(GHC)', 'temp_id': 'Vol', 
            'margin': 'Gr. Rev(GHC)', 'Name_Sales': 'Name'
        }, inplace=True)
        
        grouped['SLA_Target'] = (grouped['expected_fee_ghc'] / grouped['Val(GHC)']).fillna(0)
        grouped['Margin %'] = (grouped['Gr. Rev(GHC)'] / grouped['Val(GHC)']).fillna(0)
        grouped['Var'] = grouped['Margin %'] - grouped['SLA_Target']
        
        diff = (grouped['Margin %'] - grouped['SLA_Target']).abs()
        status_pass = diff <= ( (grouped['SLA_Target'].abs() * tolerance) + 0.0001 )
        grouped['Status'] = np.where(grouped['Tier'] == "No Tier", "No Target", np.where(status_pass, "Pass", "Fail"))
        
        final_report.append(grouped)

    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()