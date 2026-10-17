FROM python:3.12-slim

WORKDIR /app

# Empêche Python d'écrire des fichiers .pyc et active le flushing des logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

COPY . /app

EXPOSE 8080

CMD ["python", "src/serve.py", "--port", "8080", "--every", "2"]
