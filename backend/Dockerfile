FROM python:3.12-slim

# psycopg2 빌드용 시스템 라이브러리. lxml/cryptography 필요할 수 있어 build-essential도 포함.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성만 먼저 복사해 캐시 활용.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 소스 — dev 모드에서는 compose가 volume mount로 덮어쓰므로 무관.
COPY . /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# uvicorn 시작. main.py의 startup hook이 init_schema()를 호출.
# 런타임에 DATABASE_URL/REDIS_HOST/OPENAI_API_KEY는 compose가 주입.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
