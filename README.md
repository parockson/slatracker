# SLA Audit Engine - Tracker

A powerful **Streamlit-based application** for auditing Service Level Agreement (SLA) compliance across different business segments. This tool analyzes sales transactions against predefined SLA pricing tiers and generates comprehensive compliance reports with per-transaction accuracy tracking.

## 🎯 Overview

The SLA Audit Engine is designed to help organizations:
- **Validate pricing compliance** across Corporate, Retail, and SMB business segments
- **Detect pricing discrepancies** between actual and expected SLA prices
- **Handle complex tiered pricing** with percentage-based and fixed fee caps
- **Generate detailed audit reports** with transaction-level analysis
- **Manage multiple SLA configurations** through Excel-based configuration files

### Key Features

✅ **Multi-Segment Support**: Separate SLA rules for Corporate, Retail, and SMB clients  
✅ **Tiered Pricing Logic**: Handles amount-based tiers (e.g., 1-50, 50-100) with configurable caps  
✅ **Flexible Fee Calculation**: Supports both percentage-based and fixed flat fees  
✅ **Tolerance Configuration**: Built-in tolerance threshold (default 10%) for variance analysis  
✅ **Dynamic Field Mapping**: User-configurable column mapping for different data formats  
✅ **Professional Dashboard**: Modern Streamlit UI with real-time metrics and visualizations  
✅ **Comprehensive Reporting**: Excel export with detailed transaction-level audit trails  

---

## 📋 Table of Contents

1. [Installation](#installation)
2. [Project Structure](#project-structure)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Data Formats](#data-formats)
6. [Core Functionality](#core-functionality)
7. [Architecture](#architecture)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)

---

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd Sla-tracker
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment**
   
   **Windows (PowerShell):**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   
   **Windows (Command Prompt):**
   ```cmd
   venv\Scripts\activate.bat
   ```
   
   **macOS/Linux:**
   ```bash
   source venv/bin/activate
   ```

4. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the Application**
   ```bash
   streamlit run app.py
   ```

   The application will open in your default web browser at `http://localhost:8501`

---

## 📁 Project Structure

```
Sla-tracker/
├── app.py                      # Main Streamlit application entry point
├── low.py                      # Sample configuration generator (one-time setup)
├── requirements.txt            # Python package dependencies
├── LICENSE                     # Project license
├── README.md                   # This file
│
├── config/
│   ├── sla_targets.xlsx        # Excel file with SLA rules by segment
│   └── sla_targets1.xlsx       # Backup/alternative SLA configuration
│
├── data/
│   └── (empty - for user uploads)
│
└── src/
    ├── __init__.py             # Package initialization
    ├── engine.py               # Core SLA audit engine logic
    ├── data_loader.py          # Data loading and preprocessing
    └── utils.py                # Utility functions (reserved for future use)
```

### File Descriptions

| File | Purpose |
|------|---------|
| **app.py** | Streamlit UI - handles page configuration, styling, user interactions, and result display |
| **src/engine.py** | Core audit logic - SLA validation, tier matching, fee calculation with caps |
| **src/data_loader.py** | Data preprocessing - cleans CSVs and Excel files, handles whitespace and formatting |
| **src/utils.py** | Helper functions - reserved for generic utilities (logging, formatting, etc.) |
| **low.py** | Bootstrap script - generates sample SLA Excel file for initial setup |
| **config/sla_targets.xlsx** | Configuration file - defines SLA rules for each business segment |

---

## ⚙️ Configuration

### SLA Configuration File (config/sla_targets.xlsx)

The Excel configuration file contains multiple sheets (one per business segment):

#### Sheet Structure
Each sheet (Corporate, Retail, SMB) should have the following columns:

| Column | Type | Description |
|--------|------|-------------|
| **Name** | String | Client/Entity identifier (for matching with sales data) |
| **Category** | String | Transaction category (e.g., Collection, Disbursement, TopUp) |
| **Min_Amt** | Numeric | Minimum transaction amount for this tier |
| **Max_Amt** | Numeric | Maximum transaction amount for this tier |
| **Target_Value** | Numeric | Fee percentage (0-1) or flat fee amount |
| **Is_Percentage** | Boolean | TRUE for percentage fees, FALSE for flat fees |
| **Limit_Value** | Numeric | Cap/maximum fee for this tier (for % fees) |

#### Example Configuration

**Corporate Sheet:**
```
Name      | Category    | Min_Amt | Max_Amt | Target_Value | Is_Percentage | Limit_Value
----------|-------------|---------|---------|--------------|---------------|-------------
Client A  | Collection  | 0       | 1000    | 0.01          | TRUE          | 25
Client A  | Collection  | 1000    | 10000   | 0.005         | TRUE          | 75
Client A  | Disbursement| 0       | 500     | 50            | FALSE         | 50
```

### Generating Sample Configuration

To create a sample configuration file with placeholder data:

```bash
python low.py
```

This generates `config/sla_targets.xlsx` with three sheets (Corporate, Retail, SMB).

---

## 📊 Usage

### Step 1: Launch the Application

```bash
streamlit run app.py
```

### Step 2: Load SLA Configuration

1. Click **"Upload SLA Configuration"** on the sidebar
2. Select your Excel file (e.g., `config/sla_targets.xlsx`)
3. Click **"Process SLA Upload"** to validate and clean the data

### Step 3: Upload Sales Data

1. Click **"Upload Sales Data"** on the sidebar
2. Select your CSV file with transaction records
3. Configure field mappings to match your data format

### Step 4: Configure Field Mappings

Map your CSV columns to the audit engine's expected fields:

| Engine Field | Your CSV Column | Example |
|--------------|-----------------|---------|
| **segment** | Business segment column | "Corporate", "Retail", "SMB" |
| **cat** | Transaction category | "Collection", "Disbursement" |
| **debit** | Debit amount column | Numeric value |
| **credit** | Credit amount column | Numeric value |
| **margin** | Margin/fee column | Numeric value |
| **name** | Client/entity identifier | Client name or ID |

### Step 5: Run Audit

1. Adjust **Tolerance Threshold** if needed (default: 10%)
2. Click **"Run SLA Audit"** button
3. Review results in the dashboard

### Step 6: Export Results

- Download audit report as Excel file
- Results include per-transaction compliance status
- Variance analysis for discrepancy investigation

---

## 📥 Data Formats

### Sales CSV Format

Your sales data CSV should include the following columns (names can be customized):

```csv
segment,category,client_name,debit_amount,credit_amount,margin
Corporate,Collection,Client A,5000,0,45
Retail,Disbursement,Retail Shop B,0,2500,10
SMB,TopUp,SMB Client C,1500,0,5
```

**Required Columns** (names configurable):
- Business segment identifier
- Transaction category
- Client/entity name
- Transaction amounts (debit/credit)
- Actual fee/margin charged

### SLA Master Excel Format

See the [Configuration](#configuration) section above for detailed column specifications.

---

## 🔧 Core Functionality

### SLA Audit Engine (src/engine.py)

#### Main Functions

**`process_sla_upload(uploaded_file)`**
- Cleans and validates SLA configuration Excel file
- Standardizes column headers and data types
- Converts currency values and handles missing tier boundaries
- Returns: Dictionary of cleaned DataFrames (one per segment)

**`run_sla_audit(sales_df, sla_dict, user_map, tolerance=0.10)`**
- Performs comprehensive row-level SLA audit
- Maps transaction categories and segments to SLA tiers
- Calculates expected fees based on tiered pricing rules
- Handles percentage caps and flat fees
- Compares actual vs expected fees within tolerance threshold
- Returns: List of audit results with compliance status

#### Fee Calculation Logic

The engine supports two fee models:

**Percentage-based Fees with Cap:**
```
expected_fee = MIN(transaction_amount × percentage, cap)
```

**Fixed Flat Fees:**
```
expected_fee = flat_fee_amount
```

#### Tier Matching Algorithm

1. Match transaction by segment (Corporate/Retail/SMB)
2. Find matching client/entity in SLA master
3. Match transaction category
4. Find appropriate tier based on transaction amount
5. Apply pricing rules for that tier
6. Calculate expected fee

### Data Loader (src/data_loader.py)

**`load_all_slas(file_path)`**
- Loads SLA configuration from Excel file
- Caches data for performance (1 hour TTL)
- Cleans column headers and string values
- Returns: Dictionary of SLA DataFrames

**`process_sales_data(file)`**
- Reads uploaded CSV file
- Handles mixed data types in large files
- Standardizes column headers
- Strips whitespace from string columns
- Returns: Cleaned sales DataFrame

---

## 🏗️ Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ USER INPUT                                                  │
├─────────────────────┬───────────────────────────────────────┤
│ SLA Excel File      │ Sales CSV File + Field Mapping        │
└──────────┬──────────┴───────────────────────┬────────────────┘
           │                                   │
           ▼                                   ▼
    ┌──────────────────────┐        ┌──────────────────────┐
    │ process_sla_upload() │        │ process_sales_data() │
    │ (engine.py)          │        │ (data_loader.py)     │
    └──────┬───────────────┘        └──────┬───────────────┘
           │                               │
           ▼                               ▼
    ┌──────────────────────┐        ┌──────────────────────┐
    │ Cleaned SLA Dict     │        │ Cleaned Sales DF     │
    └──────┬───────────────┘        └──────┬───────────────┘
           │                               │
           └───────────────┬───────────────┘
                           │
                           ▼
                ┌──────────────────────────┐
                │ run_sla_audit()          │
                │ (engine.py)              │
                │ - Tier matching          │
                │ - Fee calculation        │
                │ - Compliance checking    │
                └──────┬───────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ Audit Results        │
            │ - Expected fees      │
            │ - Actual fees        │
            │ - Compliance status  │
            │ - Variance analysis  │
            └──────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │ Streamlit Dashboard      │
        │ - Metrics cards          │
        │ - Results table          │
        │ - Export to Excel        │
        └──────────────────────────┘
```

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Web Framework | Streamlit | Latest |
| Data Processing | Pandas | Latest |
| Numerical Computing | NumPy | Latest |
| Excel I/O | OpenPyXL | Latest |
| CSV Processing | Pandas CSV | Latest |

---

## 📚 API Reference

### engine.py

```python
def process_sla_upload(uploaded_file) -> dict:
    """
    Clean and validate SLA configuration Excel file.
    
    Args:
        uploaded_file: Streamlit UploadedFile object (Excel file)
    
    Returns:
        dict: Keys are sheet names, values are cleaned DataFrames
              Returns None if error occurs
    
    Raises:
        Exception: Caught and printed to console with error message
    """

def run_sla_audit(sales_df, sla_dict, user_map, tolerance=0.10) -> list:
    """
    Perform comprehensive SLA audit on sales transactions.
    
    Args:
        sales_df (pd.DataFrame): Sales transaction data with columns:
            - segment, raw_cat, debit_amt, credit_amt, margin
        sla_dict (dict): SLA configuration from process_sla_upload()
        user_map (dict): Field mapping {'segment': col, 'cat': col, ...}
        tolerance (float): Variance tolerance (default 0.10 = 10%)
    
    Returns:
        list: Audit records with keys:
            - __original_entity_name__: Client name
            - raw_cat: Transaction category
            - Tier: SLA tier matched
            - active_val: Transaction amount used
            - expected_fee_ghc: Calculated fee based on SLA
            - actual_fee: Fee from sales data
            - variance: Difference from expected
            - compliant: Boolean compliance status
    
    Processing Steps:
        1. Standardize sales data with user-provided field mapping
        2. Clean numeric and string columns
        3. Normalize business segment and category abbreviations
        4. Match transactions to SLA tiers by segment/client/category/amount
        5. Calculate expected fees with cap handling
        6. Compare against actual fees with tolerance threshold
        7. Aggregate results for reporting
    """
```

### data_loader.py

```python
@st.cache_data(ttl=3600)
def load_all_slas(file_path: str) -> dict:
    """
    Load and cache SLA configuration from Excel file.
    
    Args:
        file_path (str): Path to Excel file containing SLA targets
    
    Returns:
        dict: Dictionary with sheets as keys and DataFrames as values
              Returns None if file doesn't exist or error occurs
    
    Caching:
        Results cached for 1 hour (ttl=3600 seconds)
    """

def process_sales_data(file) -> pd.DataFrame:
    """
    Read, clean, and validate sales CSV file.
    
    Args:
        file: Streamlit UploadedFile object (CSV file)
    
    Returns:
        pd.DataFrame: Cleaned sales data
                     Returns None if error occurs
    
    Processing:
        - Handles mixed data types in large files (low_memory=False)
        - Strips whitespace from headers and text columns
        - Standardizes column naming
    """
```

---

## 🐛 Troubleshooting

### Common Issues

#### Issue: "Column not found" Error

**Cause**: Field mapping doesn't match your CSV columns

**Solution**:
1. Check exact column names in your CSV file (case-sensitive)
2. Remove leading/trailing spaces in column names
3. Update field mapping to match your column names
4. Verify data types (numeric columns should be numeric)

#### Issue: "No Tier" Matches for Transactions

**Cause**: Transaction amount doesn't fall within any configured tier range

**Solution**:
1. Verify SLA tiers cover expected amount ranges
2. Check Min_Amt and Max_Amt values in configuration
3. Ensure categories match exactly (case-insensitive in config)
4. Review for gaps between tier ranges (e.g., 0-1000, 2000-5000 has gap)

#### Issue: "Empty DataFrame" After Upload

**Cause**: File format or encoding issue

**Solution**:
1. Ensure Excel file has sheets named exactly: Corporate, Retail, SMB
2. Verify CSV uses UTF-8 encoding
3. Check that columns have data (not hidden rows/columns)
4. Try re-saving file in Excel/Notepad and uploading again

#### Issue: Performance Lag with Large Files

**Cause**: Large transaction volume

**Solution**:
1. Split large CSV files into multiple uploads
2. Filter sales data for specific time periods
3. Optimize SLA configuration (reduce tier complexity)
4. Increase Streamlit memory or run on more powerful machine

#### Issue: Decimal/Currency Format Issues

**Cause**: Different regional settings (e.g., , vs . for decimals)

**Solution**:
1. Export data as CSV with US locale settings
2. Ensure numeric columns are formatted as numbers
3. Remove currency symbols before upload ($, €, ₵, etc.)
4. Use . (period) as decimal separator

### Debug Mode

To enable detailed logging:

1. Open `app.py` and uncomment debug statements
2. Check Streamlit console for detailed error messages
3. Review cleaned data in memory for inspection

---

## 🔐 Security Considerations

- **Data Privacy**: All data processing happens locally; no cloud uploads
- **File Validation**: Excel and CSV files are validated before processing
- **Input Sanitization**: Column names and string values are cleaned
- **Error Handling**: Exceptions are caught to prevent app crashes

---

## 📈 Performance Metrics

| Operation | Expected Time | Max Transactions |
|-----------|---------------|------------------|
| Load SLA Config | <1s | N/A |
| Process 1000 rows | 2-5s | 10,000+ |
| Generate Report | <10s | 100,000+ |
| Cache hit (repeat audit) | <0.5s | N/A |

---

## 🎨 UI Features

### Dashboard Components

1. **Sidebar Controls**
   - SLA configuration upload
   - Sales data upload
   - Field mapping configuration
   - Tolerance adjustment slider

2. **Main Dashboard**
   - Key metrics cards (Total transactions, Compliance %, etc.)
   - Detailed results table with sorting/filtering
   - Variance analysis charts
   - Export button for Excel report

3. **Styling**
   - Modern dark theme with custom CSS
   - Responsive design for desktop and tablet
   - Real-time metric updates
   - Hover effects and animations

---

## 📝 Sample Workflows

### Workflow 1: Initial Setup

1. Run `python low.py` to generate sample configuration
2. Prepare your sales CSV with similar structure to demo data
3. Upload SLA configuration: `config/sla_targets.xlsx`
4. Upload sales data CSV
5. Configure field mappings
6. Run audit and review results

### Workflow 2: Ongoing Monitoring

1. Prepare monthly sales extract
2. Upload to application
3. Run audit with standard tolerance settings
4. Export results for compliance reporting
5. Investigate variance outliers

### Workflow 3: Configuration Tuning

1. Run audit with current configuration
2. Identify systematic variances
3. Adjust SLA tiers in Excel configuration
4. Reload configuration in app
5. Re-run audit to validate improvements

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/improvement`)
3. **Make** your changes with clear commit messages
4. **Test** thoroughly before submitting
5. **Submit** a pull request with description of changes

### Areas for Contribution

- Additional category mappings
- Enhanced error handling
- Performance optimizations
- UI/UX improvements
- Test coverage expansion
- Documentation improvements

---

## 📞 Support

For issues, questions, or suggestions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review existing GitHub issues
3. Create a new issue with detailed description
4. Provide sample data (anonymized if needed)

---

## 🗂️ Appendix

### Category Abbreviation Mapping

The engine standardizes common category names:

| Full Name | Abbreviation |
|-----------|--------------|
| Collection | col |
| Disbursement | disb |
| E-distribution | E-dis |
| Remittance | Rem |
| Airtime Purchase | TopUp |
| Data Purchase | Data |
| Utilities | UT |
| Funds Transfer | FT |
| Ticketing | TK |

### Segment Abbreviation Mapping

| Full Name | Abbreviation |
|-----------|--------------|
| Corporate | Cor |
| Retail | Self |
| SMB | Asst |

### Formula Reference

**Compliance Check Formula:**
```
Is_Compliant = |Actual_Fee - Expected_Fee| / Expected_Fee ≤ Tolerance
```

**Variance Calculation:**
```
Variance = (Actual_Fee - Expected_Fee) / Expected_Fee × 100%
```

---

## 📚 Additional Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Pandas User Guide](https://pandas.pydata.org/docs/)
- [OpenPyXL Documentation](https://openpyxl.readthedocs.io/)

---

**Last Updated**: April 2026  
**Version**: 1.0  
**Maintained By**: Prince Acquah Rockson
