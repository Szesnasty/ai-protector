# ── Stage 1: Builder ────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential g++ \
    # WeasyPrint system deps (build time)
    libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 libffi-dev libcairo2 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache . && \
    # Presidio PII needs the spaCy model — not a PyPI package, install the wheel.
    uv pip install --system --no-cache \
    "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"

# ── Stage 2: Runtime ────────────────────────────────────
FROM python:3.12-slim

# WeasyPrint runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 libcairo2 libglib2.0-0 \
    fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# ── Pre-bake the ML guard models into the image ───────────────────────
# Ships the models in the image: no runtime download, no cold-start, works in
# air-gapped / offline deployments and in CI without HF access. Both are
# ungated (Apache-2.0 / open) — no HF token needed. Keep ids in sync with
# settings.jailbreak_ml_model / settings.harm_ml_model (src/config.py).
ENV HF_HOME=/opt/hf-cache
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='madhurjindal/Jailbreak-Detector')" && \
    # Download AND smoke-test granite: run a real guardian_config inference so a
    # transformers/template incompatibility fails the BUILD, not silently in prod.
    python -c "import torch; from transformers import AutoTokenizer, AutoModelForCausalLM; m='ibm-granite/granite-guardian-3.0-2b'; tok=AutoTokenizer.from_pretrained(m); mdl=AutoModelForCausalLM.from_pretrained(m).eval(); ids=tok.apply_chat_template([{'role':'user','content':'hello'}], guardian_config={'risk_name':'harm'}, add_generation_prompt=True, return_tensors='pt', return_dict=True); mdl.generate(**ids, max_new_tokens=1); print('granite-guardian guardian_config OK')"

COPY src/ src/
COPY data/ data/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
