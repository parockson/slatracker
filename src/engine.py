import pandas as pd
import numpy as np

def process_sla_upload(uploaded_file):
    """
    Cleans and prepares the SLA Master Excel data.
    Ensures numeric columns are valid and tiers have default boundaries.
    """
    try:
        # Load all sheets from the Excel file into a dictionary of DataFrames
        sla_dict = pd.read_excel(uploaded_file, sheet_name=None)
        cleaned_dict = {}
        
        for sheet_name, df in sla_dict.items():
            # Strip leading/trailing whitespaces from column headers
            df.columns = df.columns.str.strip()
            
            # Numeric columns that need cleaning (removing currency symbols/commas)
            num_cols = ['Min_Amt', 'Max_Amt', 'Target_Value', 'Limit_Value']
            for col in num_cols:
                if col in df.columns:
                    # Convert to numeric, removing any non-digit characters except the decimal point
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            
            # Fill missing tier boundaries to ensure range comparisons don't break
            if 'Min_Amt' in df.columns: df['Min_Amt'] = df['Min_Amt'].fillna(0)
            if 'Max_Amt' in df.columns: df['Max_Amt'] = df['Max_Amt'].fillna(99999999)
            
            # Normalize the 'Is_Percentage' flag to uppercase strings for consistent logic matching
            if 'Is_Percentage' in df.columns: 
                df['Is_Percentage'] = df['Is_Percentage'].astype(str).str.upper().str.strip()
                
            # Clean string columns in the SLA table for case-insensitive matching
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
    Performs row-level analysis to handle tiered caps (e.g., 1% max GHS 25).
    """
    # 1. Pre-standardize Sales Data based on User UI Mapping
    internal_keys = {
        user_map['segment']: 'segment', 
        user_map['cat']: 'raw_cat', 
        user_map['debit']: 'debit_amt', 
        user_map['credit']: 'credit_amt',
        user_map['margin']: 'margin'
    }
    df = sales_df.rename(columns=internal_keys).copy()
    
    # Clean numeric data in sales file
    for col in ['debit_amt', 'credit_amt', 'margin']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)

    # Standardize abbreviations for matching
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

    # 2. Process each Segment Sheet in SLA Master
    for original_tab_name, sla_table in sla_dict.items():
        tab_name_low = original_tab_name.lower()
        seg_mask = df['segment_low'] == tab_name_low
        seg_data = df[seg_mask].copy()
        if seg_data.empty: continue
            
        # Get dynamic entity column name (Name/Client/etc)
        ent_col_raw = user_map.get(original_tab_name)
        seg_data['__original_entity_name__'] = sales_df.loc[seg_data.index, ent_col_raw]
        seg_data['ent_low'] = seg_data['__original_entity_name__'].astype(str).str.strip().str.lower()
        
        # Select active transaction amount: Debit for Corporate, Credit for Retail/SMB
        current_seg_abbr = seg_map.get(tab_name_low, original_tab_name)
        seg_data['active_val'] = seg_data['debit_amt'] if current_seg_abbr == 'Cor' else seg_data['credit_amt']
        seg_data['temp_id'] = range(len(seg_data))

        # Find the matching column in SLA table
        name_col_sla = next((c for c in sla_table.columns if c.lower().strip() in ['name', 'client', 'disbursement channel name']), None)
        if not name_col_sla: continue

        # Merge sales with SLA rules (Cartesian match for tiers)
        merged = seg_data.merge(
            sla_table, 
            left_on=['raw_cat_low', 'ent_low'], 
            right_on=['Category', name_col_sla], 
            how='left'
        )

        # Filter to find the correct tier based on transaction amount
        tier_match_mask = (merged['active_val'] >= merged['Min_Amt']) & (merged['active_val'] <= merged['Max_Amt'])
        matches = merged[tier_match_mask].copy()
        
        # Isolate transactions that didn't find an SLA match
        matched_temp_ids = matches['temp_id'].unique()
        no_matches = seg_data[~seg_data['temp_id'].isin(matched_temp_ids)].copy()
        
        if not no_matches.empty:
            no_matches['Tier'] = "No Tier"
            # Set defaults for non-matches to prevent calculation errors
            no_matches['Target_Value'], no_matches['Is_Percentage'], no_matches['Limit_Value'] = 0, "TRUE", 99999999
            processed_data = pd.concat([matches, no_matches], ignore_index=True)
        else:
            processed_data = matches

        # Create textual tier label (e.g., T (1-50))
        processed_data['Tier'] = np.where(processed_data['Tier'] == "No Tier", "No Tier", 
            "T (" + processed_data['Min_Amt'].astype(int).astype(str) + "-" + processed_data['Max_Amt'].astype(int).astype(str) + ")")

        # --- ROW-LEVEL TARGET CALCULATION (Handling Caps) ---
        def calculate_expected_fee(row):
            if row['Tier'] == "No Tier": return 0
            
            val = row['active_val']
            target = float(row.get('Target_Value', 0))
            is_pct = str(row.get('Is_Percentage', 'TRUE')).upper() == "TRUE"
            cap = row.get('Limit_Value', 99999999) # Use Limit_Value from Excel
            
            # Default logic if cap is missing or zero in Excel
            if pd.isna(cap) or cap == 0: cap = 99999999
            
            if is_pct:
                # Core logic: If % fee exceeds cap, use cap. Else use % fee.
                calculated_fee = val * target
                return min(calculated_fee, cap)
            else:
                # Fixed Flat Fee logic
                return target

        # Execute calculation for every row individually
        processed_data['expected_fee_ghc'] = processed_data.apply(calculate_expected_fee, axis=1)

        # 3. Group and Aggregate Results for Report
        grouped = processed_data.groupby(['Biz seg', 'Cat', '__original_entity_name__', 'Tier']).agg({
            'active_val': 'sum',      # Total GHC value
            'temp_id': 'count',       # Volume (count)
            'margin': 'sum',          # Actual Revenue
            'expected_fee_ghc': 'sum' # Calculated/Capped Target Revenue
        }).reset_index()

        grouped.rename(columns={'active_val': 'Val(GHC)', 'temp_id': 'Vol', 'margin': 'Gr. Rev(GHC)', '__original_entity_name__': 'Name'}, inplace=True)
        
        # Calculate Effective Percentages for comparison
        # This turns GHS fees back into % so we can see variance
        grouped['SLA_Target'] = (grouped['expected_fee_ghc'] / grouped['Val(GHC)']).fillna(0)
        grouped['Margin %'] = (grouped['Gr. Rev(GHC)'] / grouped['Val(GHC)']).fillna(0)
        grouped['Var'] = grouped['Margin %'] - grouped['SLA_Target']
        
        # Determine Pass/Fail Status based on tolerance
        diff = (grouped['Margin %'] - grouped['SLA_Target']).abs()
        # If difference is within X% of the target, mark as Pass
        status_pass = diff <= ( (grouped['SLA_Target'].abs() * tolerance) + 0.0001 )
        
        grouped['Status'] = np.where(grouped['Tier'] == "No Tier", "No Target", np.where(status_pass, "Pass", "Fail"))
        grouped['SLA_Target'] = grouped['SLA_Target'].round(4)
        
        final_report.append(grouped)

    # Combine all segments (Corporate, Retail, SMB) into final output
    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()