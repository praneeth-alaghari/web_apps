# 💰 Statement Analyzer

A smart, web-based financial statement parser that extracts transactions from **bank statements** (PDF & CSV), categorizes spending, and generates **interactive visual reports** — all in seconds, entirely in-browser.

> **Why this exists:** Manually reviewing bank statements is tedious and error-prone. This tool automates the process with intelligent parsing strategies that handle everything from clean CSV exports to messy, unstructured PDF extractions.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **Dual-format support** | Accepts both `.pdf` and `.csv` bank statement files |
| **Intelligent auto-detection** | Automatically selects the right parsing strategy based on file structure |
| **Smart categorization** | Classifies transactions into Food, Transport, Shopping, Entertainment, Bills, Transfers, and more |
| **Interactive charts** | Doughnut chart for category breakdown + bar chart for spending trends (weekly/monthly) |
| **Sortable transaction log** | Full transaction table with column sorting (date, description, category, amount) |
| **Robust date parsing** | Handles diverse date formats with fuzzy matching and validation |
| **Containerized** | Ships with a production-ready `Dockerfile` for one-command deployment |

---

## 🏗️ Architecture

```
statement_analyzer/
├── app.py                 # Flask application — routes, parsing engine, analytics
├── templates/
│   ├── index.html         # Upload interface with drag-and-drop support
│   └── result.html        # Analysis dashboard with Chart.js visualizations
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container configuration (Python 3.11-slim)
├── .gitignore
└── .dockerignore
```

### Parsing Pipeline

The core engine uses a **strategy pattern** to handle structurally different statements:

```
Upload → Format Detection → Strategy Selection → Transaction Extraction → Analytics → Visualization
```

| Strategy | Trigger | Handles |
|---|---|---|
| **Tabular** | Named columns detected (`date`, `description`, `debit`, etc.) | HDFC, SBI, ICICI, Axis CSV exports and well-structured PDFs |
| **Messy PDF** | Positional/unnamed columns | PhonePe, GPay, Paytm statement PDFs with irregular layouts |

---

## 🛠️ Tech Stack

- **Backend:** Python 3.11, Flask
- **PDF Extraction:** pdfplumber (text-layer extraction with configurable table settings)
- **Data Processing:** pandas, python-dateutil
- **Frontend:** Vanilla HTML/CSS/JS, Chart.js
- **Containerization:** Docker (multi-stage ready)

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+ (or Docker)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/praneeth-alaghari/web_apps.git
cd web_apps/statement_analyzer

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

The app will be available at **http://localhost:8000**

### Docker

```bash
# Build the image
docker build -t statement-analyzer .

# Run the container
docker run -p 8000:8000 statement-analyzer
```

---

## 📊 How It Works

1. **Upload** a bank statement (PDF or CSV) via the web interface
2. The engine **auto-detects** the file structure and selects the appropriate parsing strategy
3. Transactions are **extracted**, validated, and classified into spending categories
4. A visual **dashboard** is generated with:
   - Total debits & credits summary
   - Top 5 merchants by spend
   - Category breakdown (doughnut chart)
   - Weekly/monthly spending trends (bar chart)
   - Complete sortable transaction log

### Category Classification

Transactions are categorized using **keyword matching** against merchant descriptions:

| Category | Example Keywords |
|---|---|
| Food | Swiggy, Zomato, McDonald's, grocery, café |
| Transport | Uber, Ola, petrol, IRCTC, flight |
| Shopping | Amazon, Flipkart, Myntra, retail |
| Entertainment | Netflix, Spotify, BookMyShow |
| Bills | Electricity, recharge, EMI, insurance |
| Transfer | UPI, PhonePe, wallet, add money |

---

## 📂 Supported Statement Formats

| Source | Format | Status |
|---|---|---|
| HDFC Bank | CSV | ✅ Tested |
| SBI | CSV | ✅ Supported |
| ICICI Bank | CSV | ✅ Supported |
| Axis Bank | CSV | ✅ Supported |
| PhonePe | PDF | ✅ Tested |
| Google Pay | PDF | ✅ Supported |
| Paytm | PDF | ✅ Supported |
| Generic bank exports | CSV/PDF | ✅ Auto-detected |

---

## 🔧 Configuration

| Parameter | Default | Description |
|---|---|---|
| `host` | `0.0.0.0` | Server bind address |
| `port` | `8000` | Server port |
| `debug` | `True` | Flask debug mode (disable in production) |

---

## 📁 Project Structure — Deep Dive

### `app.py` — Core Module

| Function | Purpose |
|---|---|
| `clean_amount()` | Sanitizes and parses currency strings (handles ₹, commas, edge cases) |
| `categorize_merchant()` | Maps merchant descriptions to spending categories |
| `_safe_parse_date()` | Robust date parser with fuzzy matching and junk rejection |
| `_process_tabular()` | Strategy 1 — parses clean, column-named data |
| `_process_messy_pdf()` | Strategy 2 — positional scanning for unstructured PDF tables |
| `process_dataframe()` | Dispatcher — auto-selects the right parsing strategy |
| `extract_tables_from_pdf()` | Multi-page PDF table extraction via pdfplumber |
| `_compute_summary()` | Aggregates parsed data into summary statistics |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-parser`)
3. Commit your changes (`git commit -m 'Add XYZ bank parser'`)
4. Push to the branch (`git push origin feature/new-parser`)
5. Open a Pull Request

---

## 📜 License

This project is open source and available for personal and educational use.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/praneeth-alaghari">Praneeth Alaghari</a>
</p>
