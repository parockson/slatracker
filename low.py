import pandas as pd

# Define sample SLA data for each segment
data = {
    "Corporate": pd.DataFrame({"Product_ID": ["A1", "B2"], "Min_SLA_Price": [100, 200]}),
    "Retail": pd.DataFrame({"Product_ID": ["A1", "B2"], "Min_SLA_Price": [120, 240]}),
    "SMB": pd.DataFrame({"Product_ID": ["A1", "B2"], "Min_SLA_Price": [110, 220]})
}

# Save to the config folder we created earlier
with pd.ExcelWriter("config/sla_targets.xlsx") as writer:
    for sheet_name, df in data.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print("✅ config/sla_targets.xlsx created with Corporate, Retail, and SMB sheets.")