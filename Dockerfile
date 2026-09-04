FROM python:3.12-slim

# gcc + headers are only needed to build the C extension at image
# build time - nothing here needs a compiler at runtime
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[web]"

EXPOSE 8000
CMD ["uvicorn", "healthunpacked.api:app", "--host", "0.0.0.0", "--port", "8000"]
