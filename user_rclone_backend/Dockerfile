# Use official Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app
# Install system dependencies and rclone
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        unzip && \
    curl -fsSL https://rclone.org/install.sh | bash && \
    apt-get purge -y curl unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*
# Copy requirements first for better caching
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .


# Run the application
CMD ["python", "-m", "api.main"]
        