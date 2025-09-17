FROM python:3.11-slim

# Install ffmpeg and other deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Good practice: create downloads dir and ensure permissions
RUN mkdir -p /app/downloads

CMD ["python", "bot.py"]
