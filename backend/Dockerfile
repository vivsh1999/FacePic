# Backend Dockerfile
FROM python:3.12-slim

# Install system dependencies for face_recognition (dlib)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-python-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir setuptools -r requirements.txt

# Install face_recognition_models from git (required for face_recognition)
RUN pip install git+https://github.com/ageitgey/face_recognition_models

# Copy application code
COPY . .

# Create directories for uploads and thumbnails
RUN mkdir -p uploads thumbnails/images thumbnails/faces

# Expose port
EXPOSE 8000

# Command for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
