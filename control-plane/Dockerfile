ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .

RUN useradd --system --uid 10001 --no-create-home appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
