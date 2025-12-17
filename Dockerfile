# AIOps Proactive Workflow Container
# For deployment on AWS ECS (triggered by EventBridge)

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy configuration
COPY config/ ./config/

# Copy source code
COPY src/ ./src/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the proactive workflow
CMD ["python", "-m", "src.main"]
