FROM python:3.12.12-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
