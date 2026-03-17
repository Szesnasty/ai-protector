FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pure-python-agent/pyproject.toml .
RUN pip install --no-cache-dir .

# Copy shared tools
COPY shared/ /app/shared/

# Copy agent code
COPY pure-python-agent/ /app/

EXPOSE 8003
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
