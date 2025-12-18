# Backend Production Dockerfile
FROM python:3.12-slim

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
# Use cache mount to speed up pip installs
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create directories for uploads and thumbnails
RUN mkdir -p uploads thumbnails/images thumbnails/faces

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
