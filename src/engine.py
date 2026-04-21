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
            # Strip leading/trailing whitespaces from column headers for consistency
            df.columns = df.columns.str.strip()
            
            # Numeric columns that need cleaning (removing currency symbols/commas)
            num_cols = ['Min_Amt', 'Max_Amt', 'Target_Value', 'Limit_Value']
            for col in num_cols:
                if col in df.columns:
                    # Convert string representations of numbers to actual floats, coercing errors to NaN
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            
            # Fill missing tier boundaries to ensure comparisons don't break during audit
            # If Min_Amt is missing, assume 0. If Max_Amt is missing, assume a very large number.
            if 'Min_Amt' in df.columns: df['Min_Amt'] = df['Min_Amt'].fillna(0)
            if 'Max_Amt' in df.columns: df['Max_Amt'] = df['Max_Amt'].fillna(99999999)
            
            # Normalize the 'Is_Percentage' flag to uppercase strings (e.g., 'TRUE' or 'FALSE')
            if 'Is_Percentage' in df.columns: 
                df['Is_Percentage'] = df['Is_Percentage'].astype(str).str.upper().str.strip()
                
            # Clean all string columns in the SLA table for faster and case-insensitive matching
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
                
            cleaned_dict[sheet_name.strip()] = df
        return cleaned_dict
    except Exception as e:
        # Gracefully handle any read exceptions
        print(f"Error in process_sla_upload: {e}")
        return None

def run_sla_audit(sales_df, sla_dict, user_map, tolerance=0.10):
    """
    Vectorized Audit Logic:
    Dramatically faster version using merges and vectorized operations instead of row-wise apply.
    """
    # ==========================================
    # 1. Pre-standardize Sales Data
    # ==========================================
    # Map the user-selected columns to internal standardized keys
    internal_keys = {
        user_map['segment']: 'segment', 
        user_map['cat']: 'raw_cat', 
        user_map['debit']: 'debit_amt', 
        user_map['credit']: 'credit_amt',
        user_map['margin']: 'margin'
    }
    # Create a working copy of the dataset with standardized column names
    df = sales_df.rename(columns=internal_keys).copy()
    
    # Clean numeric data once by removing all non-numeric characters except dots and minus signs
    for col in ['debit_amt', 'credit_amt', 'margin']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)

    # Global Mapping Dictionaries for categorizing transactions
    # These dictionaries map various representations of user data to internal abbreviations
    cat_map = {
        'collection': 'col', 'disbursement': 'disb', 'disbursement 1': 'disb',
        'e-distribution': 'E-dis', 'remittance': 'Rem', 'disbursement 2': 'Rem',
        'airtime purchase': 'TopUp', 'data purchase': 'Data', 'utilities': 'UT',
        'funds transfer': 'FT', 'ticketing': 'TK'
    }
    seg_map = {'corporate': 'Cor', 'retail': 'Self', 'smb': 'Asst'}
    
    # Pre-clean string columns (lowercase and stripped) for accurate matching against SLA tables
    df['segment_low'] = df['segment'].astype(str).str.strip().str.lower()
    df['raw_cat_low'] = df['raw_cat'].astype(str).str.strip().str.lower()
    
    # Apply abbreviations using the global mapping dicts. If no match is found, keep original text
    df['Cat'] = df['raw_cat_low'].map(cat_map).fillna(df['raw_cat'])
    df['Biz seg'] = df['segment_low'].map(seg_map).fillna(df['segment'])

    final_report = []

    # ==========================================
    # 2. Process each Segment Sheet
    # ==========================================
    # Iterate through each tab uploaded in the SLA master Excel file
    for original_tab_name, sla_table in sla_dict.items():
        tab_name_low = original_tab_name.lower()
        
        # Filter the sales data to only match the current SLA segment tab being processed
        seg_mask = df['segment_low'] == tab_name_low
        seg_data = df[seg_mask].copy()
        if seg_data.empty: continue
            
        # Extract the original entity column based on the user's mapping for this tab
        ent_col_raw = user_map.get(original_tab_name)
        
        # Store the original entity name securely to avoid column name collisions during merges
        seg_data['__original_entity_name__'] = sales_df.loc[seg_data.index, ent_col_raw]
        seg_data['ent_low'] = seg_data['__original_entity_name__'].astype(str).str.strip().str.lower()
        
        # Determine the active value (Debit vs Credit) based on the current segment
        # Corporate (Cor) uses Debit, others use Credit
        current_seg_abbr = seg_map.get(tab_name_low, original_tab_name)
        seg_data['active_val'] = seg_data['debit_amt'] if current_seg_abbr == 'Cor' else seg_data['credit_amt']

        # Vectorized Tier Matching
        # dynamically find the target entity-name column in the SLA table (e.g., 'Name', 'Client', etc.)
        name_col_sla = next((c for c in sla_table.columns if c.lower().strip() in ['name', 'client', 'disbursement channel name']), None)
        
        if not name_col_sla:
            continue

        # Merge sales with SLA rules on Category and Entity Name
        # This creates a Cartesian product for any matches (multiple SLA tiers per entity)
        merged = seg_data.merge(
            sla_table, 
            left_on=['raw_cat_low', 'ent_low'], 
            right_on=['Category', name_col_sla], 
            how='left'
        )

        # Filter the merged dataframe to ensure the transaction amount falls into the correct SLA tier
        # Note: Some transactions might not match any tier
        tier_match_mask = (merged['active_val'] >= merged['Min_Amt']) & (merged['active_val'] <= merged['Max_Amt'])
        
        matches = merged[tier_match_mask].copy()
        
        # Identify non-matches by establishing a temporary tracking ID
        all_ids = set(seg_data.index)
        matched_ids = set(matches.index) # This is index relative to 'merged' not 'seg_data'
        
        # Assign unique sequence index to track transactions before merging
        seg_data['temp_id'] = range(len(seg_data))
        
        # Re-merge to properly filter matched tiers vs unmatched transactions
        merged = seg_data.merge(
            sla_table, 
            left_on=['raw_cat_low', 'ent_low'], 
            right_on=['Category', name_col_sla], 
            how='left'
        )
        
        tier_match_mask = (merged['active_val'] >= merged['Min_Amt']) & (merged['active_val'] <= merged['Max_Amt'])
        matches = merged[tier_match_mask].copy()
        
        # Format the textual representation of the Tier sequence
        matches['Tier'] = "T (" + matches['Min_Amt'].astype(int).astype(str) + "-" + matches['Max_Amt'].astype(int).astype(str) + ")"
        matches['T_Val'] = matches['Target_Value']
        matches['Is_P'] = matches['Is_Percentage']
        
        # Handle "No Tier" cases - isolate transactions that didn't match any SLA tier rule
        matched_temp_ids = matches['temp_id'].unique()
        no_matches = seg_data[~seg_data['temp_id'].isin(matched_temp_ids)].copy()
        if not no_matches.empty:
            no_matches['Tier'] = "No Tier"
            no_matches['T_Val'] = 0
            no_matches['Is_P'] = "TRUE" # Default value format
            # Combine successful SLA matches with unmatched transactions
            processed_data = pd.concat([matches, no_matches], ignore_index=True)
        else:
            processed_data = matches

        # ==========================================
        # 3. Group and Calculate Performance
        # ==========================================
        # Group by the defining dimensions and aggregate amounts and transaction counts
        grouped = processed_data.groupby(['Biz seg', 'Cat', '__original_entity_name__', 'Tier', 'T_Val', 'Is_P']).agg({
            'active_val': 'sum',   # Total transaction amount
            'temp_id': 'count',    # Transaction volume (count)
            'margin': 'sum'        # Total gross revenue fetched
        }).reset_index()

        # Rename aggregated columns to match final report layout
        grouped.rename(columns={'active_val': 'Val(GHC)', 'temp_id': 'Vol', 'margin': 'Gr. Rev(GHC)', '__original_entity_name__': 'Name'}, inplace=True)
        
        # Vectorized Performance Calculation
        # Establish masking variables for logic calculation
        is_pct = grouped['Is_P'].astype(str).str.upper() == "TRUE"
        no_tier = grouped['Tier'] == "No Tier"
        
        # Target Margin calculation logic:
        # If no tier, 0. If it's a fixed flat percentage, use it directly.
        # If it's a fixed flat rate (e.g. 5 GHC per trans), calculate target % equivalent based on Total_Amt / Volume = (Vol * Target_Rate)/Total_Amount
        grouped['target_pct'] = np.where(
            no_tier, 0,
            np.where(
                is_pct, grouped['T_Val'],
                np.where(grouped['Val(GHC)'] > 0, (grouped['Vol'] * grouped['T_Val']) / grouped['Val(GHC)'], 0)
            )
        )
        
        # Calculate the actual achieved margin percent
        grouped['actual_margin'] = np.where(grouped['Val(GHC)'] > 0, grouped['Gr. Rev(GHC)'] / grouped['Val(GHC)'], 0)
        
        # Determine Pass/Fail status
        # A transaction block passes if the absolute difference is within the assigned sensitivity tolerance
        diff = (grouped['actual_margin'] - grouped['target_pct']).abs()
        status_pass = diff <= ( (grouped['target_pct'].abs() * tolerance) + 0.0001 )
        
        # Final variable assignments
        grouped['SLA_Target'] = grouped['target_pct'].round(4)
        grouped['Status'] = np.where(no_tier, "No Target", np.where(status_pass, "Pass", "Fail"))
        grouped['Margin %'] = grouped['actual_margin']
        grouped['Var'] = grouped['Margin %'] - grouped['SLA_Target']
        
        # Append the segment's analysis back to the final master report list
        final_report.append(grouped)

    # Recombine all segment reports into one grand dataframe
    return pd.concat(final_report, ignore_index=True) if final_report else pd.DataFrame()