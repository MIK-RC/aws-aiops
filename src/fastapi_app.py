"""
Primary FastAPI Application to invoke AWS AgentCore Application deployed on AWS. Uses

"""

import json
import os

import boto3
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response

# Load .env credentials
load_dotenv()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
}
PORT = 8000
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION")
AGENTCORE_AGENT_RUNTIME_ARN = os.environ.get(
    "AGENTCORE_AGENT_RUNTIME_ARN"
)  # Get from AgentCore UI on AWS.
app = FastAPI()


@app.post("/invoke")
async def invoke_agent(request: Request):
    """
    Mirrors lambda_handler POST logic exactly
    """
    body = await request.json()

    client = boto3.client(
        "bedrock-agentcore",
        region_name=AWS_REGION,
    )

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENTCORE_AGENT_RUNTIME_ARN,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(body).encode("utf-8"),
    )

    result = response["response"].read().decode("utf-8")

    return Response(
        content=result,
        status_code=200,
        headers=CORS_HEADERS,
        media_type="application/json",
    )


if __name__ == "__main__":
    uvicorn.run(
        "app:app",  # module_name:app_instance
        host="0.0.0.0",
        port=PORT,
        reload=False,  # reload=True breaks when run this way
        log_level="info",
    )
