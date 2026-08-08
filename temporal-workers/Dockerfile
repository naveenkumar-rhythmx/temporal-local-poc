FROM python:3.11-slim

WORKDIR /app
COPY temporal-workers/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY temporal-workflows/workflows ./workflows
COPY temporal-workers/worker ./worker
ENV PYTHONPATH=/app

CMD ["python", "worker/main.py"]
