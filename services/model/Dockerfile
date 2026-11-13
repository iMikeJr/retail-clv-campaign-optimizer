FROM python:3.12.12-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
COPY *.py schema.sql .
CMD ["python", "main.py"]
