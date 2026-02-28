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
    val = str(val).strip().replace(',', '')
    # Remove currency symbols if present
    match = re.search(r'[-+]?\d*\.\d+|\d+', val)
    if match:
        try:
            return float(val)
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
        'bills': ['electricity', 'water', 'internet', 'mobile', 'recharge', 'broadband', 'insurance', 'emi', 'loan']
    }
    for cat, keywords in categories.items():
        if any(keyword in merchant for keyword in keywords):
            return cat.capitalize()
    return 'Other'

def process_dataframe(df):
    # Standardize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # Try to find standard columns
    date_col = next((c for c in df.columns if 'date' in c), None)
    desc_col = next((c for c in df.columns if any(x in c for x in ['desc', 'particulars', 'narration', 'merchant', 'details'])), None)
    
    # Amount columns can be single amount or split debit/credit
    debit_col = next((c for c in df.columns if 'debit' in c or 'withdrawal' in c or 'out' in c), None)
    credit_col = next((c for c in df.columns if 'credit' in c or 'deposit' in c or 'in' in c), None)
    amount_col = next((c for c in df.columns if 'amount' in c), None)
    
    if not date_col or not desc_col:
        raise ValueError("Could not find standard Date and Description columns in the file.")
        
    if not (debit_col and credit_col) and not amount_col:
        raise ValueError("Could not find standard Amount or Debit/Credit columns in the file.")

    processed = pd.DataFrame()
    
    # Parse Dates
    processed['Date'] = df[date_col].apply(lambda x: parser.parse(str(x), fuzzy=True) if pd.notna(x) else pd.NaT)
    processed = processed.dropna(subset=['Date'])
    
    processed['Description'] = df[desc_col].fillna("Unknown")
    processed['Category'] = processed['Description'].apply(categorize_merchant)
    
    if debit_col and credit_col:
        processed['Debit'] = df[debit_col].apply(clean_amount)
        processed['Credit'] = df[credit_col].apply(clean_amount)
    else:
        # We only have one amount column, assume negative is debit or we need to infer
        temp_amount = df[amount_col].apply(lambda x: clean_amount(x) if pd.notna(x) else 0.0)
        # Try to infer if positive means debit or credit. Usually bank statements have separate columns if both exist.
        # If it's a credit card, positive usually means debit (spend), negative means credit (payment).
        processed['Debit'] = temp_amount.apply(lambda x: x if x > 0 else 0)
        processed['Credit'] = temp_amount.apply(lambda x: abs(x) if x < 0 else 0)

    # Calculate summary
    total_debit = processed['Debit'].sum()
    total_credit = processed['Credit'].sum()
    
    # Top 5 Merchants by Spending (Debit)
    top_merchants = processed[processed['Debit'] > 0].groupby('Description')['Debit'].sum().nlargest(5).to_dict()
    
    # Category Breakdown (Debit)
    category_breakdown = processed[processed['Debit'] > 0].groupby('Category')['Debit'].sum().to_dict()
    
    # Spends over time
    processed['YearMonth'] = processed['Date'].dt.to_period('M')
    processed['YearWeek'] = processed['Date'].dt.to_period('W')
    processed['Year'] = processed['Date'].dt.to_period('Y')
    
    date_range_days = (processed['Date'].max() - processed['Date'].min()).days
    
    if date_range_days <= 60:
        # Weekly if ~2 months or less
        time_spends = processed[processed['Debit'] > 0].groupby(processed['YearWeek'].astype(str))['Debit'].sum().to_dict()
        time_label = "Weekly Spends"
    elif date_range_days <= 400:
        # Monthly if ~1 year or less
        time_spends = processed[processed['Debit'] > 0].groupby(processed['YearMonth'].astype(str))['Debit'].sum().to_dict()
        time_label = "Monthly Spends"
    else:
        # Yearly
        time_spends = processed[processed['Debit'] > 0].groupby(processed['Year'].astype(str))['Debit'].sum().to_dict()
        time_label = "Yearly Spends"
        
    return {
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "top_merchants": {k: round(v, 2) for k, v in top_merchants.items()},
        "category_breakdown": {k: round(v, 2) for k, v in category_breakdown.items()},
        "time_spends": {k: round(v, 2) for k, v in time_spends.items()},
        "time_label": time_label
    }

def extract_tables_from_pdf(file_stream):
    dfs = []
    with pdfplumber.open(file_stream) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if len(table) > 1:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    # Basic check to see if it looks like a transaction table
                    col_str = " ".join([str(c).lower() for c in df.columns])
                    if 'date' in col_str and ('amount' in col_str or 'debit' in col_str):
                        dfs.append(df)
    
    if not dfs:
        raise ValueError("No valid transaction tables found in PDF.")
    
    return pd.concat(dfs, ignore_index=True)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    logger.info("Received POST request on /analyze route.")
    if 'statement_file' not in request.files:
        logger.warning("No file part in the request.")
        flash('No file uploaded')
        return redirect(url_for('index'))
        
    file = request.files['statement_file']
    if file.filename == '':
        logger.warning("No file selected by user.")
        flash('No selected file')
        return redirect(url_for('index'))
        
    logger.info(f"Processing uploaded file: {file.filename}")
    
    try:
        filename_lower = file.filename.lower()
        if filename_lower.endswith('.csv'):
            logger.info("File identified as CSV. Parsing with pandas.")
            try:
                stream = io.StringIO(file.stream.read().decode("utf8"), newline=None)
                df = pd.read_csv(stream)
                logger.info(f"CSV Parsed. Shape: {df.shape}")
            except Exception as e:
                logger.error(f"Error reading CSV: {e}", exc_info=True)
                raise ValueError("Failed to read CSV. Ensure it is a valid comma-separated file.")
                
        elif filename_lower.endswith('.pdf'):
            logger.info("File identified as PDF. Extracting tables with pdfplumber.")
            try:
                stream = io.BytesIO(file.read())
                df = extract_tables_from_pdf(stream)
                logger.info(f"PDF Parsed. Shape: {df.shape}")
            except Exception as e:
                logger.error(f"Error reading PDF: {e}", exc_info=True)
                raise ValueError("Failed to extract tables from PDF.")
        else:
            logger.warning("Unsupported file format uploaded.")
            flash('Unsupported file format. Please upload PDF or CSV.')
            return redirect(url_for('index'))
            
        logger.info("Starting dataframe processing.")
        result = process_dataframe(df)
        logger.info("Dataframe processed successfully. Rendering results.")
        
        return render_template("result.html", result=result)
        
    except Exception as e:
        logger.error(f"General error during processing: {str(e)}", exc_info=True)
        flash(f"Error processing file: {str(e)}")
        return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
