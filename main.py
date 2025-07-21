#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-genai>=1.23.0",
#     "python-dotenv>=1.1.1",
#     "asyncio>=3.4.3",
# ]
# ///

"""
Main script for the datasheetminer API.

This script is used to test the API locally.

It loads the environment variables from the .env file and uses the lambda_handler function to generate a response.

The script takes a prompt as input and uses the Gemini API to generate a response to the prompt based on the content of the document.

"""

import os
import asyncio
from dotenv import load_dotenv
from datasheetminer.app import lambda_handler

# Load environment variables
load_dotenv()

CONTEXT_PROMPT = "Identify the product and technology along with key specifications."
# ANALYSIS_PROMPT = "Extract the specification parameters outlined for the product variations as a JSON object with pre-defined default values."
# EXTRACTION_PROMPT = "Extract the specification values for each part number as a JSON object."

async def main():
    # Check if API key is configured
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY not found in environment. Please add it to your .env file.")
        return
    
    response = await lambda_handler({
        "body": {
            "prompt": CONTEXT_PROMPT,
            "url": "https://acim.nidec.com/drives/control-techniques/-/media/Project/Nidec/ControlTechniques/Documents/Datasheets/Digitax-HD-Datasheet.pdf"
        },
        "headers": {
            "Authorization": f"Bearer {os.getenv('GEMINI_API_KEY')}"
        }
    }, {})
    
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
