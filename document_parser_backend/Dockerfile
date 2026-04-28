# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for your packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

    
# Copy requirements first for better caching
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN pip install mistralai langchain-text-splitters

# Copy the entire project
COPY . .

# Expose the port your Flask app runs on
EXPOSE 4999

# Run the application
CMD ["python", "-u", "run.py"]