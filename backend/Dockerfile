FROM python:3.11-slim-bookworm

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (psycopg2-binary doesn't need compilation)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
