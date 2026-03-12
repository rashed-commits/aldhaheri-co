FROM python:3.11-slim

RUN useradd -m appuser

WORKDIR /app

RUN mkdir -p /data && chown appuser:appuser /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser

EXPOSE 4001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4001"]
