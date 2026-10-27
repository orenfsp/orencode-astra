FROM python:3.12-slim AS runtime

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

FROM python:3.12-slim AS test

WORKDIR /app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY tests ./tests

RUN pip install --no-cache-dir ".[test]"

CMD ["sh", "-c", "alembic upgrade head && alembic upgrade head && alembic check && python -m app.seed && python -m app.seed && python -m app.create_admin && python -m unittest discover -s tests -v"]
