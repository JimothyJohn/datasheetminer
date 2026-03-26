"""
Intake pipeline — scans incoming PDFs in S3 triage/ for table of contents
and specification data, promotes valid datasheets to good_examples/,
and creates Datasheet records in DynamoDB.

Flow:
    upload → triage/ → scan for TOC/specs → good_examples/ + Datasheet → extract

Usage (via dsm-agent):
    dsm-agent intake-list                    # list PDFs in triage/
    dsm-agent intake <s3_key> --type motor   # scan + promote one PDF
    dsm-agent intake-all                     # scan all PDFs in triage/
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from pydantic import BaseModel, Field

log = logging.getLogger("dsm-agent.intake")

# Gemini model for lightweight triage scanning
_TRIAGE_MODEL = "gemini-2.5-flash"

_TRIAGE_PROMPT = """Analyze this PDF document and determine if it is a valid industrial product datasheet.

Check for:
1. A table of contents that references specification sections or data tables
2. Technical specification tables with numeric values and units
3. Product identification information (manufacturer, model numbers)

If EITHER a table of contents referencing specs OR specification data tables are present,
this is a valid datasheet.

Extract the following metadata from the document:
- product_type: one of "motor", "drive", "gearhead", "robot_arm", "factory" (pick the best match)
- manufacturer: the company that makes the product
- product_name: the product name or model series
- product_family: the product family or sub-series (if identifiable)
- category: a brief category description (e.g., "brushless dc motor", "servo drive")
- spec_pages: list of page numbers that contain specification tables (1-indexed)

Be conservative: only mark is_valid_datasheet=false if the document clearly has NO
technical specifications or product data whatsoever (e.g., marketing brochures with
no specs, instruction manuals, safety notices).
"""


class IntakeScanResult(BaseModel):
    """Lightweight scan result from Gemini triage."""

    is_valid_datasheet: bool = Field(
        ..., description="Whether this PDF contains specification data"
    )
    has_table_of_contents: bool = Field(
        ..., description="Whether a TOC referencing specs was found"
    )
    has_specification_tables: bool = Field(
        ..., description="Whether data tables with specs were found"
    )
    product_type: str | None = Field(None, description="Detected product type")
    manufacturer: str | None = Field(None, description="Detected manufacturer name")
    product_name: str | None = Field(None, description="Detected product name or model")
    product_family: str | None = Field(None, description="Detected product family")
    category: str | None = Field(None, description="Brief category description")
    spec_pages: list[int] | None = Field(
        None, description="Page numbers containing specification tables"
    )
    rejection_reason: str | None = Field(
        None, description="Why the PDF was rejected (if not valid)"
    )


def scan_pdf(pdf_bytes: bytes, api_key: str) -> IntakeScanResult:
    """Run a lightweight Gemini scan to check for TOC and spec tables.

    Sends the PDF with a triage-specific prompt and returns structured
    metadata about whether the document is a valid datasheet.
    """
    from google import genai

    client = genai.Client(api_key=api_key)

    contents = [
        genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        _TRIAGE_PROMPT,
    ]

    log.info("Scanning PDF (%d bytes) for TOC and spec tables", len(pdf_bytes))

    response = client.models.generate_content(
        model=_TRIAGE_MODEL,
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_schema": IntakeScanResult,
        },
    )

    import json

    raw = json.loads(response.text)
    result = IntakeScanResult.model_validate(raw)

    log.info(
        "Scan result: valid=%s toc=%s tables=%s type=%s mfg=%s name=%s",
        result.is_valid_datasheet,
        result.has_table_of_contents,
        result.has_specification_tables,
        result.product_type,
        result.manufacturer,
        result.product_name,
    )
    return result


def promote_pdf(
    bucket: str,
    triage_key: str,
    scan: IntakeScanResult,
    *,
    s3_client: Any = None,
    dynamo_client: Any = None,
) -> dict[str, Any]:
    """Move a validated PDF from triage/ to good_examples/ and create a Datasheet record.

    Returns a summary dict with the new S3 key and datasheet_id.
    """
    from datasheetminer.models.datasheet import Datasheet

    if s3_client is None:
        import boto3

        s3_client = boto3.client(
            "s3", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )

    if dynamo_client is None:
        from datasheetminer.db.dynamo import DynamoDBClient

        table = os.environ.get("DYNAMODB_TABLE_NAME", "products")
        dynamo_client = DynamoDBClient(table_name=table)

    # Build good_examples/ key from triage/ key
    filename = triage_key.rsplit("/", 1)[-1]
    datasheet_id = uuid.uuid4()
    good_key = f"good_examples/{datasheet_id}/{filename}"

    # Move PDF: copy then delete
    s3_client.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": triage_key},
        Key=good_key,
    )
    s3_client.delete_object(Bucket=bucket, Key=triage_key)
    log.info("Moved %s -> %s", triage_key, good_key)

    # Create Datasheet record
    datasheet = Datasheet(
        datasheet_id=datasheet_id,
        url=f"s3://{bucket}/{good_key}",
        pages=scan.spec_pages,
        product_type=scan.product_type or "motor",
        product_name=scan.product_name or filename.replace(".pdf", ""),
        product_family=scan.product_family,
        manufacturer=scan.manufacturer or "Unknown",
        category=scan.category,
        status="approved",
        s3_key=good_key,
    )

    dynamo_client.create(datasheet)
    log.info(
        "Created Datasheet %s — %s by %s (%s)",
        datasheet_id,
        datasheet.product_name,
        datasheet.manufacturer,
        datasheet.product_type,
    )

    return {
        "datasheet_id": str(datasheet_id),
        "s3_key": good_key,
        "product_type": datasheet.product_type,
        "product_name": datasheet.product_name,
        "manufacturer": datasheet.manufacturer,
        "product_family": datasheet.product_family,
        "category": datasheet.category,
        "spec_pages": scan.spec_pages,
        "status": "approved",
    }


def intake_single(
    bucket: str,
    triage_key: str,
    api_key: str,
    *,
    s3_client: Any = None,
    dynamo_client: Any = None,
) -> dict[str, Any]:
    """Full intake flow for one PDF: download → scan → promote or reject."""
    if s3_client is None:
        import boto3

        s3_client = boto3.client(
            "s3", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )

    # Download
    log.info("Downloading s3://%s/%s", bucket, triage_key)
    resp = s3_client.get_object(Bucket=bucket, Key=triage_key)
    pdf_bytes: bytes = resp["Body"].read()

    # Scan
    scan = scan_pdf(pdf_bytes, api_key)

    if not scan.is_valid_datasheet:
        log.warning(
            "Rejected %s: %s",
            triage_key,
            scan.rejection_reason or "not a valid datasheet",
        )
        return {
            "s3_key": triage_key,
            "status": "rejected",
            "reason": scan.rejection_reason or "no specification data found",
            "has_toc": scan.has_table_of_contents,
            "has_spec_tables": scan.has_specification_tables,
        }

    # Promote
    result = promote_pdf(
        bucket, triage_key, scan, s3_client=s3_client, dynamo_client=dynamo_client
    )
    result["status"] = "approved"
    return result


def list_triage(bucket: str, *, s3_client: Any = None) -> list[dict[str, Any]]:
    """List all PDFs in the triage/ prefix."""
    if s3_client is None:
        import boto3

        s3_client = boto3.client(
            "s3", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )

    items: list[dict[str, Any]] = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix="triage/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                items.append(
                    {
                        "s3_key": key,
                        "size_bytes": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                    }
                )
    return items
