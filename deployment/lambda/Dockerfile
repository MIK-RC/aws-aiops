# Lambda Deployment Dockerfile
# For container-based Lambda deployment

FROM public.ecr.aws/lambda/python:3.12

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements and install dependencies
COPY deployment/lambda/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target .

# Copy configuration files
COPY config/ ./config/

# Copy source code
COPY src/ ./src/

# Copy the Lambda handler
COPY deployment/lambda/handler.py .

# Set environment variables
ENV AIOPS_CONFIG_DIR=/var/task/config
ENV PYTHONPATH=/var/task

# Command for the Lambda runtime
CMD ["handler.handler"]
