FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY common ./common
COPY services/maintenance/ ./
RUN mkdir -p /app/instance

EXPOSE 5000

# Контекст сборки — корень репозитория: docker build -f services/maintenance/Dockerfile .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "maintenance_app:app"]
