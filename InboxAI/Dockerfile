FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Render PORT
EXPOSE 10000

# Create a startup script to run both services
# Streamlit uses PORT env variable provided by Render or defaults to 10000
# FastAPI runs on 8001 locally inside the container
RUN echo '#!/bin/bash\n\
uvicorn backend:app --host 0.0.0.0 --port 8001 &\n\
PORT=${PORT:-10000}\n\
streamlit run app.py --server.port $PORT --server.address 0.0.0.0\n\
' > /app/start.sh

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
