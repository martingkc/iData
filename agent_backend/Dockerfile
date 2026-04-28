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


RUN apt-get update && apt-get install -y \
    nodejs \
    npm 
RUN npm install -g mcp-remote 

    
# Copy requirements first for better caching
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt 

RUN pip install psycopg2-binary
RUN pip install PyJWT
RUN pip install flask-cors flask_httpauth langgraph-checkpoint-postgres "psycopg[binary,pool]" langchain-mcp-adapters




COPY . .

# Expose the port your Flask app runs on
EXPOSE 5001

# Run the application
CMD ["python", "-u", "run.py"]