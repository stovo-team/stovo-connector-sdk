FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY connector.py main.py ./

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["python", "main.py"]
