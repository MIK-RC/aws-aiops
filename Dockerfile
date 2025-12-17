# AIOps Proactive Workflow - AgentCore Runtime
# Deployed on AWS Bedrock AgentCore

FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy configuration
COPY config/ ./config/

# Copy source code
COPY src/ ./src/

# Set environment variables
ENV PYTHONPATH=${LAMBDA_TASK_ROOT}
ENV PYTHONUNBUFFERED=1
ENV AIOPS_CONFIG_DIR=${LAMBDA_TASK_ROOT}/config

# AgentCore entry point
CMD ["src.main.invoke"]
