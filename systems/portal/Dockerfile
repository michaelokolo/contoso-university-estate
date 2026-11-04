# Contoso portal (vendor SaaS). Build context is the REPO ROOT, so it can include seed data.
# Generate data first (python data-generator/generate.py), then build.
FROM python:3.12-slim
WORKDIR /app
COPY systems/portal/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY systems/common ./common
COPY systems/portal .
COPY output/portal/applications.jsonl ./seed/applications.jsonl
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
