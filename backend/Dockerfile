FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system vallet && adduser --system --ingroup vallet vallet

COPY requirements.lock pyproject.toml alembic.ini ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY app ./app
RUN pip install --no-cache-dir --no-deps .

USER vallet

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
