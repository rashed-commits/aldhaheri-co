FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create runtime directories (volumes will overlay these in production)
RUN mkdir -p data/raw model/saved output logs

# Container stays alive for `docker exec` cron invocations
CMD ["tail", "-f", "/dev/null"]
