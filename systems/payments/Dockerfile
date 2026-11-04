# Contoso payments (vendor SaaS). Build context is the REPO ROOT, so it can include seed data.
# Generate data first (python data-generator/generate.py), then build.
FROM python:3.12-slim
WORKDIR /app
COPY systems/payments/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY systems/common ./common
COPY systems/payments .

ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
