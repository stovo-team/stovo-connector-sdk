FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# Create directory for mounted connector plugins
RUN mkdir -p /connectors

EXPOSE 8080

CMD ["stovo-connector", "host", "--dir", "/connectors", "--host", "0.0.0.0", "--port", "8080"]
