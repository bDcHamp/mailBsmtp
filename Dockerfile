FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose internal web port
EXPOSE 8085

ENV PORT=8085
ENV HOST=0.0.0.0
ENV AUTO_START_ENGINE=true

CMD ["python", "run_web.py", "--port", "8085", "--host", "0.0.0.0"]

