FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias pesadas primero (mejor cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=300 \
    numpy==1.26.4 \
    pandas==2.2.3
RUN pip install --no-cache-dir --timeout=300 \
    tensorflow==2.18.0
RUN pip install --no-cache-dir --timeout=300 \
    -r requirements.txt

# Descargar recursos NLTK en tiempo de build
RUN python -c "import nltk; nltk.download('vader_lexicon', quiet=True); nltk.download('punkt', quiet=True)" || true

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/ || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
