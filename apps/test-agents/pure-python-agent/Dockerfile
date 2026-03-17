FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy shared tools first (referenced as `shared.*`)
COPY ../shared ./shared

# Copy agent code
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
