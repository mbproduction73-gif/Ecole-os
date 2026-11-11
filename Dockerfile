FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ecom_os ./ecom_os
COPY templates ./templates
RUN mkdir -p data logs && useradd -m app && chown -R app /app
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn ecom_os.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
