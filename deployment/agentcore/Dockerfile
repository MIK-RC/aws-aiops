# AgentCore Deployment Dockerfile
# Based on AWS Lambda Python 3.12 base image

FROM public.ecr.aws/lambda/python:3.12

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements and install dependencies
COPY deployment/agentcore/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target .

# Copy configuration files
COPY config/ ./config/

# Copy source code
COPY src/ ./src/

# Copy the main application
COPY deployment/agentcore/app.py .

# Set environment variables
ENV AIOPS_CONFIG_DIR=/var/task/config
ENV PYTHONPATH=/var/task

# Command to run the application
CMD ["app.invoke"]
