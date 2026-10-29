FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir asyncpg==0.30.0
COPY migrate.py ./migrate.py
COPY migrations ./migrations
RUN useradd -r -u 10001 vigia
USER vigia
ENTRYPOINT ["python","migrate.py"]
