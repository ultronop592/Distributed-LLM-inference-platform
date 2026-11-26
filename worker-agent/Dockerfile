ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY agent.py .

RUN useradd --system --uid 10001 --no-create-home appuser
USER appuser

CMD ["python", "agent.py"]
