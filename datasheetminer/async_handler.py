"""
Async processing handler for long-running datasheet analysis.
"""

import json
import uuid
import boto3
import os
from typing import Dict, Any


def queue_analysis(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Queue long-running analysis and return job ID immediately.

    For prompts/documents that might take >25 seconds, this endpoint
    queues the work and returns a job ID for status checking.
    """
    try:
        # Parse request
        body = (
            json.loads(event.get("body", "{}"))
            if isinstance(event.get("body"), str)
            else event.get("body", {})
        )
        headers = event.get("headers", {})

        # Extract parameters
        prompt = body.get("prompt", "")
        url = body.get("url", "")
        api_key = headers.get("x-api-key", "")

        # Validate
        if not api_key or not api_key.strip():
            return {
                "statusCode": 401,
                "body": json.dumps(
                    {
                        "error": {
                            "type": "authentication_error",
                            "message": "API key required",
                        }
                    }
                ),
            }

        # Generate job ID
        job_id = str(uuid.uuid4())

        # Queue for processing (using SQS)
        if os.environ.get("ANALYSIS_QUEUE_URL"):
            sqs = boto3.client("sqs")
            sqs.send_message(
                QueueUrl=os.environ["ANALYSIS_QUEUE_URL"],
                MessageBody=json.dumps(
                    {
                        "job_id": job_id,
                        "prompt": prompt,
                        "url": url,
                        "api_key": api_key,
                        "timestamp": context.aws_request_id,
                    }
                ),
            )

            return {
                "statusCode": 202,  # Accepted
                "body": json.dumps(
                    {
                        "job_id": job_id,
                        "status": "queued",
                        "message": f"Analysis queued. Check status at /status/{job_id}",
                        "estimated_time": "30-120 seconds",
                    }
                ),
            }
        else:
            # Fallback - process immediately but warn about timeout risk
            from .gemini import analyze_document

            result = analyze_document(prompt, url, api_key)

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {"job_id": job_id, "status": "completed", "message": result.text}
                ),
            }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def check_status(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Check analysis job status."""
    try:
        job_id = event.get("pathParameters", {}).get("job_id")

        if not job_id:
            return {"statusCode": 400, "body": json.dumps({"error": "job_id required"})}

        # Check DynamoDB for job status (would need to implement)
        # For now, return placeholder
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "job_id": job_id,
                    "status": "processing",
                    "message": "Job status checking not yet implemented",
                }
            ),
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
