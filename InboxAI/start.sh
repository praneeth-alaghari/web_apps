#!/bin/bash
# Start the FastAPI backend in the background
uvicorn backend:app --host 0.0.0.0 --port 8001 &

# Start the Streamlit frontend in the foreground, using Render's provided $PORT
PORT=${PORT:-10000}
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
