import io
import re
import math
import logging
import pdfplumber
import pandas as pd
from dateutil import parser
from flask import Flask, render_template, request, flash, redirect, url_for

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_in_production'


def clean_amount(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip().replace(',', '').replace('₹', '')
    match = re.search(r'[-+]?\d*\.\d+|\d+', val_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return 0.0
    return 0.0

def categorize_merchant(merchant):
    merchant = str(merchant).lower()
    categories = {
        'food': ['restaurant', 'cafe', 'swiggy', 'zomato', 'mcdonalds', 'kfc', 'food', 'dominos', 'coffee', 'grocery', 'supermarket', 'mart'],
        'transport': ['uber', 'ola', 'taxi', 'petrol', 'fuel', 'transit', 'rail', 'irctc', 'flight'],
        'shopping': ['amazon', 'flipkart', 'myntra', 'shopping', 'store', 'mall', 'retail'],
        'entertainment': ['netflix', 'spotify', 'movie', 'cinema', 'bookmyshow', 'game'],
        'bills': ['electricity', 'water', 'internet', 'mobile', 'recharge', 'broadband', 'insurance', 'emi', 'loan'],
        'transfer': ['up', 'transfer', 'add money', 'upi', 'phonepe', 'wallet']
    }
    for cat, keywords in categories.items():
        if any(keyword in merchant for keyword in keywords):
            return cat.capitalize()
    return 'Other'


# ─────────────────────────────────────────────────────────────
# CORE: Robust date parser
# ─────────────────────────────────────────────────────────────
def _safe_parse_date(val):
    """Robust date parsing that handles various formats and rejects junk."""
    val_str = str(val).strip().lower().replace('nan', '').replace('none', '')
    if not val_str:
        return pd.NaT
    try:
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        has_month = any(m in val_str for m in months)
        has_year = bool(re.search(r'\d{4}', val_str))
        has_date_pattern = bool(re.search(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', val_str))

        if not has_month and not has_year and not has_date_pattern:
            return pd.NaT
        if re.fullmatch(r'[\d\s:amp\.]+', val_str) and ':' in val_str:
            return pd.NaT

        p_dt = parser.parse(val_str, fuzzy=True, dayfirst=True)
        if p_dt.year < 2010:
            return pd.NaT
        return p_dt
    except:
        return pd.NaT


# ─────────────────────────────────────────────────────────────
# CORE: Helpers for messy PDF scanning
# ─────────────────────────────────────────────────────────────
def _scan_type_amount(vals, start=0):
    """Scan all columns for a type keyword (DEBIT/CREDIT/DR/CR) and an amount (₹)."""
    type_str = ""
    amt = 0
    for ci in range(start, len(vals)):
        v = str(vals[ci]).strip().upper()
        if v in ['DEBIT', 'CREDIT', 'RECEIVED', 'PAID', 'SENT', 'REFUND', 'DR', 'CR', 'WITHDRAWAL', 'DEPOSIT']:
            type_str = v
        if '₹' in v or (type_str and ci > 0):
            test_amt = clean_amount(v)
            if test_amt > 0:
                amt = test_amt
    return type_str, amt


def _classify_amount(type_str, amt):
    """Classify an amount as debit or credit based on the type keyword."""
    debit_kw = ['DEBIT', 'PAID', 'WITHDRAWAL', 'SENT', 'DR']
    credit_kw = ['CREDIT', 'RECEIVED', 'DEPOSIT', 'REFUND', 'CR']

    debit = amt if any(x in type_str for x in debit_kw) else 0
    credit = amt if any(x in type_str for x in credit_kw) else 0

    if debit == 0 and credit == 0:
        debit = amt  # default to debit if unknown
    return debit, credit


# ─────────────────────────────────────────────────────────────
# STRATEGY 1: Clean tabular data (CSV, well-structured PDFs)
#   Works with: HDFC, SBI, ICICI, Axis CSV exports, etc.
# ─────────────────────────────────────────────────────────────
def _process_tabular(df):
    """Process clean tabular data where columns have meaningful names."""
    cols = list(df.columns)

    date_col = next((c for c in cols if any(x in c for x in ['date', 'txn date', 'value date', 'trans date'])), None)
    desc_col = next((c for c in cols if any(x in c for x in ['description', 'desc', 'details', 'narration', 'particulars', 'merchant', 'transaction'])), None)

    debit_col = next((c for c in cols if any(x in c for x in ['debit', 'withdrawal', 'dr', 'paid', 'spent']) and 'type' not in c), None)
    credit_col = next((c for c in cols if any(x in c for x in ['credit', 'deposit', 'cr', 'received', 'income']) and 'type' not in c), None)
    amount_col = next((c for c in cols if any(x in c for x in ['amount', 'value', 'amt']) and 'type' not in c), None)
    type_col = next((c for c in cols if any(x in c for x in ['type', 'dr/cr', 'transaction type'])), None)

    logger.info(f"Tabular mapping: date={date_col}, desc={desc_col}, debit={debit_col}, credit={credit_col}, amount={amount_col}, type={type_col}")

    if not date_col or not desc_col:
        raise ValueError(f"Could not find Date and Description columns. Found: {cols}")
    if not debit_col and not credit_col and not amount_col:
        raise ValueError(f"Could not find Amount/Debit/Credit columns. Found: {cols}")

    processed_rows = []
    for _, row in df.iterrows():
        dt = _safe_parse_date(row.get(date_col))
        if pd.isna(dt):
            continue

        desc = str(row.get(desc_col, '')).strip()
        if not desc or desc.lower() in ['nan', 'none', '']:
            continue

        if debit_col and credit_col:
            debit = clean_amount(row.get(debit_col, 0))
            credit = clean_amount(row.get(credit_col, 0))
        elif amount_col and type_col:
            amt = clean_amount(row.get(amount_col, 0))
            type_val = str(row.get(type_col, '')).upper()
            if any(x in type_val for x in ['CR', 'CREDIT', 'RECEIVED', 'DEPOSIT', 'REFUND']):
                debit, credit = 0, amt
            else:
                debit, credit = amt, 0
        elif amount_col:
            amt = clean_amount(row.get(amount_col, 0))
            debit, credit = amt, 0
        else:
            continue

        if debit <= 0 and credit <= 0:
            continue

        processed_rows.append({
            'Date': dt, 'Description': desc,
            'Category': categorize_merchant(desc),
            'Debit': float(debit), 'Credit': float(credit)
        })

    return processed_rows


# ─────────────────────────────────────────────────────────────
# STRATEGY 2: Messy PDF extraction (positional scanning)
#   Works with: PhonePe, GPay, Paytm PDFs, etc.
# ─────────────────────────────────────────────────────────────
def _process_messy_pdf(df):
    """Process messy PDF data where columns are positionally indexed."""

    # Try to find header row by scanning data
    date_idx, desc_idx, type_idx, amt_idx = None, None, None, None

    for idx, row in df.iterrows():
        row_str = " ".join([str(x).lower() for x in row.values])
        if 'date' in row_str and ('transaction' in row_str or 'details' in row_str):
            row_vals = [str(x).lower() for x in row.values]
            date_idx = next((i for i, v in enumerate(row_vals) if 'date' in v or 'dat' == v), None)
            desc_idx = next((i for i, v in enumerate(row_vals) if 'transaction' in v or 'details' in v or 'desc' in v or 'narr' in v), None)
            type_idx = next((i for i, v in enumerate(row_vals) if 'type' in v or 'dr/cr' in v), None)
            amt_idx = next((i for i, v in enumerate(row_vals) if 'amount' in v or 'amou' in v or 'amt' in v), None)
            break

    # Fallback defaults
    if date_idx is None: date_idx = 0
    if desc_idx is None: desc_idx = min(2, len(df.columns) - 1)
    if type_idx is None:
        type_idx = next((i for i, v in enumerate(df.columns) if 'type' in str(v).lower()), min(4, len(df.columns) - 1))
    if amt_idx is None:
        amt_idx = next((i for i, v in enumerate(df.columns) if 'amou' in str(v).lower() or 'amt' in str(v).lower()), len(df.columns) - 1)

    logger.info(f"Messy PDF indices - Date: {date_idx}, Desc: {desc_idx}, Type: {type_idx}, Amt: {amt_idx}")

    processed_rows = []

    for _, row in df.iterrows():
        vals = list(row.values)
        if len(vals) < 3:
            continue

        # 1. Date reconstruction
        raw_date_str = str(vals[date_idx])
        if date_idx + 1 < len(vals):
            next_val = str(vals[date_idx + 1]).strip()
            if next_val and (re.search(r'\d{4}', next_val) or any(m in next_val.lower() for m in ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])):
                raw_date_str += f" {next_val}"

        dt = _safe_parse_date(raw_date_str)

        # Edge case: entire transaction crammed into col_0
        if pd.isna(dt) and len(str(vals[0])) > 15:
            col0_str = str(vals[0])
            date_match = re.match(r'([A-Za-z]{3}\s+\d{1,2},?\s*\d{4})', col0_str)
            if date_match:
                dt = _safe_parse_date(date_match.group(1))
                if not pd.isna(dt):
                    remaining_desc = col0_str[date_match.end():].strip()
                    if remaining_desc:
                        type_str, amt = _scan_type_amount(vals, start=1)
                        if amt > 0:
                            debit, credit = _classify_amount(type_str, amt)
                            processed_rows.append({
                                'Date': dt, 'Description': remaining_desc,
                                'Category': categorize_merchant(remaining_desc),
                                'Debit': float(debit), 'Credit': float(credit)
                            })
                            continue

        if pd.isna(dt):
            continue

        # 2. Description reconstruction - merge text columns until type/amount keyword
        desc_parts = []
        for ci in range(desc_idx, len(vals)):
            v = str(vals[ci]).strip()
            if v.upper() in ['DEBIT', 'CREDIT', 'RECEIVED', 'PAID', 'SENT', 'REFUND', 'DR', 'CR']:
                break
            if '₹' in v:
                break
            if v.lower() not in ['nan', 'none', '']:
                desc_parts.append(v)
        desc = " ".join(desc_parts).strip()

        # Fallback: extract description from col_0 after the date portion
        if not desc:
            col0_str = str(vals[0])
            date_match = re.match(r'[A-Za-z]{3}\s+\d{1,2},?\s*\d{4}', col0_str)
            if date_match:
                desc = col0_str[date_match.end():].strip()

        if not desc or desc.lower() in ['transaction details', 'date transaction', 'details']:
            continue

        # 3. Amount parsing - scan ALL columns
        type_str, amt = _scan_type_amount(vals)

        # Fallback: try fixed indices
        if amt <= 0 and len(vals) > amt_idx:
            combined = f"{str(vals[type_idx])} {str(vals[amt_idx])}"
            amt = clean_amount(combined)

        if amt <= 0:
            continue

        debit, credit = _classify_amount(type_str, amt)

        processed_rows.append({
            'Date': dt, 'Description': desc,
            'Category': categorize_merchant(desc),
            'Debit': float(debit), 'Credit': float(credit)
        })

    return processed_rows


# ─────────────────────────────────────────────────────────────
# SUMMARY: Compute stats from parsed transactions
# ─────────────────────────────────────────────────────────────
def _compute_summary(processed):
    """Compute summary statistics from the processed transactions DataFrame."""
    total_debit = processed['Debit'].sum()
    total_credit = processed['Credit'].sum()
    top_merchants = processed[processed['Debit'] > 0].groupby('Description')['Debit'].sum().nlargest(5).to_dict()
    category_breakdown = processed[processed['Debit'] > 0].groupby('Category')['Debit'].sum().to_dict()

    processed['Date_Str'] = processed['Date'].dt.strftime('%Y-%m-%d')

    date_range_days = (processed['Date'].max() - processed['Date'].min()).days
    if date_range_days <= 60:
        time_spends = processed[processed['Debit'] > 0].groupby(processed['Date'].dt.to_period('W').astype(str))['Debit'].sum().to_dict()
        time_label = "Weekly Spends"
    else:
        time_spends = processed[processed['Debit'] > 0].groupby(processed['Date'].dt.to_period('M').astype(str))['Debit'].sum().to_dict()
        time_label = "Monthly Spends"

    return {
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "top_merchants": {k: round(v, 2) for k, v in top_merchants.items()},
        "category_breakdown": {k: round(v, 2) for k, v in category_breakdown.items()},
        "time_spends": {k: round(v, 2) for k, v in time_spends.items()},
        "time_label": time_label,
        "transactions": [{**r, 'Date': r['Date_Str']} for r in processed.to_dict('records')]
    }


# ─────────────────────────────────────────────────────────────
# DISPATCHER: Auto-detects the right strategy
# ─────────────────────────────────────────────────────────────
def process_dataframe(df):
    logger.info(f"Processing dataframe: {len(df)} rows, {len(df.columns)} cols.")

    # Standardize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_str = " ".join(list(df.columns))

    # Detect strategy based on column names
    has_named_date = any(x in col_str for x in ['date', 'txn date', 'value date'])
    has_named_desc = any(x in col_str for x in ['description', 'desc', 'details', 'narration', 'particulars', 'merchant', 'transaction'])
    has_named_amounts = any(x in col_str for x in ['debit', 'credit', 'withdrawal', 'deposit', 'amount', 'dr', 'cr'])

    if has_named_date and has_named_desc and has_named_amounts:
        logger.info("STRATEGY: Clean tabular data (CSV / well-formed PDF)")
        processed_rows = _process_tabular(df)
    else:
        logger.info("STRATEGY: Messy PDF data (positional scanning)")
        processed_rows = _process_messy_pdf(df)

    processed = pd.DataFrame(processed_rows)
    if processed.empty:
        raise ValueError("No valid transactions could be parsed. Please check the file format.")

    logger.info(f"Parsed {len(processed)} verified transactions.")
    return _compute_summary(processed)


# ─────────────────────────────────────────────────────────────
# PDF EXTRACTION
# ─────────────────────────────────────────────────────────────
def extract_tables_from_pdf(file_stream):
    all_rows = []
    logger.info("Starting robust multi-page PDF extraction...")
    try:
        with pdfplumber.open(file_stream) as pdf:
            for i, page in enumerate(pdf.pages):
                table_settings = {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_y_tolerance": 7,
                    "intersection_x_tolerance": 25,
                    "join_tolerance": 5
                }
                tables = page.extract_tables(table_settings=table_settings)
                for table in tables:
                    if table and len(table) >= 1:
                        all_rows.extend(table)
                logger.info(f"Page {i+1} processed. Total raw rows so far: {len(all_rows)}")
    except Exception as e:
        logger.error(f"Error during PDF extraction: {e}")
        raise ValueError(f"Failed to extract tables: {str(e)}")

    if not all_rows:
        raise ValueError("No data found in PDF.")

    max_cols = max(len(r) for r in all_rows)
    df = pd.DataFrame(all_rows, columns=[f"col_{i}" for i in range(max_cols)])
    return df


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    logger.info("Received POST request on /analyze route.")
    if 'statement_file' not in request.files:
        flash('No file uploaded')
        return redirect(url_for('index'))

    file = request.files['statement_file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    logger.info(f"Processing uploaded file: {file.filename}")

    try:
        filename_lower = file.filename.lower()
        if filename_lower.endswith('.csv'):
            logger.info("File identified as CSV.")
            try:
                stream = io.StringIO(file.stream.read().decode("utf8"), newline=None)
                df = pd.read_csv(stream)
                logger.info(f"CSV Parsed. Shape: {df.shape}")
            except Exception as e:
                raise ValueError("Failed to read CSV. Ensure it is a valid comma-separated file.")

        elif filename_lower.endswith('.pdf'):
            logger.info("File identified as PDF.")
            try:
                stream = io.BytesIO(file.read())
                df = extract_tables_from_pdf(stream)
                logger.info(f"PDF Parsed. Shape: {df.shape}")
            except Exception as e:
                raise ValueError(f"Failed to extract tables from PDF: {str(e)}")
        else:
            flash('Unsupported file format. Please upload PDF or CSV.')
            return redirect(url_for('index'))

        result = process_dataframe(df)
        return render_template("result.html", result=result)

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        flash(f"Error processing file: {str(e)}")
        return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
