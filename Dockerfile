FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements/all.txt /app/requirements/all.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements/all.txt

COPY . /app

CMD ["uvicorn", "echomind.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
