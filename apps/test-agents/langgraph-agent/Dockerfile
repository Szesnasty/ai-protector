FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY langgraph-agent/pyproject.toml .
RUN pip install --no-cache-dir .

# Copy shared tools
COPY shared/ /app/shared/

# Copy agent code
COPY langgraph-agent/ /app/

EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
