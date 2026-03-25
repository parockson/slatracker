"""
Sample Configuration Generator - SLA Price Tracker

This script generates a sample SLA target Excel file (`config/sla_targets.xlsx`) 
with placeholder data for Corporate, Retail, and SMB segments. 
This is useful for initializing the application and demonstrating its functionality.
"""

import pandas as pd

# Define sample SLA data for each business segment
data = {
    "Corporate": pd.DataFrame({"Product_ID": ["A1", "B2"], "Min_SLA_Price": [100, 200]}),
    "Retail": pd.DataFrame({"Product_ID": ["A1", "B2"], "Min_SLA_Price": [120, 240]}),
    "SMB": pd.DataFrame({"Product_ID": ["A1", "B2"], "Min_SLA_Price": [110, 220]})
}

# Ensure the config directory exists before saving (done manually or by app.py)
# Save the sample data to an Excel file with multiple sheets
with pd.ExcelWriter("config/sla_targets.xlsx") as writer:
    for sheet_name, df in data.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print("✅ config/sla_targets.xlsx created with Corporate, Retail, and SMB sheets.")