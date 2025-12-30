# Use an official Python 3.12 image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create a volume for the database and portfolio file
VOLUME /app/data

# Ensure the database URL points to the volume if not already handled by env
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/trading.db

# Expose the web dashboard port
EXPOSE 8000

# Set environment variables (placeholders, should be provided at runtime)
ENV OPENROUTER_API_KEY=""
ENV MARKET_DATA_API_KEY="yahoo"

# Run the application
ENTRYPOINT ["python", "-m", "src.main"]
