# QuantDinger Backend API Dockerfile
# BASE_IMAGE can be overridden from docker-compose (e.g. IMAGE_PREFIX for mirror pulls).
ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE}

WORKDIR /app

# Apt: use official Debian repositories. This server is on a US network; avoid CN mirrors.
RUN set -eux; \
    APT_TIMEOUT='Acquire::http::Timeout=35'; \
    apt-get -o "$APT_TIMEOUT" -o Acquire::https::Timeout=35 -o Acquire::ForceIPv4=true update; \
    apt-get install -y --no-install-recommends --fix-missing \
      ca-certificates \
      curl \
      build-essential \
      python3-dev \
      libffi-dev \
      libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Pip: use the default PyPI index.
RUN set -eux; \
    pip install --no-cache-dir --prefer-binary --timeout 180 -r requirements.txt; \
    apt-get purge -y --auto-remove build-essential python3-dev libffi-dev libssl-dev; \
    rm -rf /var/lib/apt/lists/*

COPY . .

COPY docker-entrypoint.sh /usr/local/bin/
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

RUN mkdir -p logs data/memory

EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV PYTHON_API_HOST=0.0.0.0
ENV PYTHON_API_PORT=5000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn_config.py", "run:app"]
