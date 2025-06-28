#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-genai>=1.23.0",
#     "python-dotenv>=1.1.1",
# ]
# ///

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import httpx

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DOC_URL = "https://acim.nidec.com/drives/control-techniques/-/media/Project/Nidec/ControlTechniques/Documents/Datasheets/Digitax-HD-Datasheet.pdf"
CONTEXT_PROMPT = "Identify the product and technology along with key specifications."
ANALYSIS_PROMPT = "Extract the specification parameters outlined for the product variations as a JSON object with pre-defined default values."
EXTRACTION_PROMPT = "Extract the specification values for each part number as a JSON object."


# Retrieve and encode the PDF byte
doc_data = httpx.get(DOC_URL).content

def get_response(prompt):
    return client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(
                data=doc_data,
                mime_type='application/pdf',
            ),
            prompt
        ]
    )

def main():
    response = get_response(CONTEXT_PROMPT)
    print(response.text)
    response = get_response(f"{response.text}\n\n{ANALYSIS_PROMPT}")
    print(response.text)
    response = get_response(f"{response.text}\n\n{EXTRACTION_PROMPT}")
    print(response.text)


if __name__ == "__main__":
    main()
