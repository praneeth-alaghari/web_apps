"""
Thin Streamlit page wrapper — delegates to training/page.py
"""
import sys
import os

# Add project root to path so training module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import training.page
training.page.render()
