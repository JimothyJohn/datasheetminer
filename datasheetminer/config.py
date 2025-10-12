from typing import Type

from pydantic import BaseModel
from datasheetminer.models.drive import Drive
from datasheetminer.models.motor import Motor


GUARDRAILS = """
"""

MODEL = "gemini-2.5-flash"  # Explicitly define model for clarity
SCHEMA_CHOICES: dict[str, Type[BaseModel]] = {
    "motor": Motor,
    "drive": Drive,
}
