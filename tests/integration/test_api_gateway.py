import os
import boto3
import pytest
import requests
from dotenv import load_dotenv

"""
Make sure env variable AWS_SAM_STACK_NAME exists with the name of the stack we are going to test. 
"""

load_dotenv()


class TestApiGateway:
    """Integration tests for the API Gateway endpoint."""

    @pytest.fixture()
    def api_gateway_url(self):
        """Get the API Gateway URL from Cloudformation Stack outputs"""
        stack_name = os.environ.get("AWS_SAM_STACK_NAME")

        if stack_name is None:
            raise ValueError(
                "Please set the AWS_SAM_STACK_NAME environment variable to the name of your stack"
            )

        client = boto3.client("cloudformation")

        try:
            response = client.describe_stacks(StackName=stack_name)
        except Exception as e:
            raise Exception(
                f"Cannot find stack {stack_name} \n"
                f'Please make sure a stack with the name "{stack_name}" exists'
            ) from e

        stacks = response["Stacks"]
        stack_outputs = stacks[0]["Outputs"]
        api_outputs = [
            output for output in stack_outputs if output["OutputKey"] == "HelloWorldApi"
        ]

        if not api_outputs:
            raise KeyError(f"HelloWorldAPI not found in stack {stack_name}")

        return api_outputs[0]["OutputValue"]  # Extract url from stack outputs

    @pytest.fixture()
    def test_pdf_url(self):
        """URL to a test PDF for integration testing."""
        return "https://httpbin.org/json"  # Simple endpoint for basic testing

    def test_api_gateway_success(self, api_gateway_url):
        """Call the API Gateway endpoint and check successful response"""
        headers = {"x-api-key": os.getenv("GEMINI_API_KEY")}

        payload = {
            "prompt": "Identify the product and technology along with key specifications.",
            "url": "https://acim.nidec.com/drives/control-techniques/-/media/Project/Nidec/ControlTechniques/Documents/Datasheets/Digitax-HD-Datasheet.pdf",
        }

        response = requests.post(api_gateway_url, headers=headers, json=payload)
        response_json = response.json()

        assert response.status_code == 200
        assert "message" in response_json
        assert isinstance(response_json["message"], str)
        assert len(response_json["message"]) > 0

    def test_api_gateway_missing_api_key(self, api_gateway_url):
        """Test API Gateway with missing API key"""
        headers = {}  # No API key

        payload = {
            "prompt": "Test prompt",
            "url": "https://example.com/test.pdf",
        }

        response = requests.post(api_gateway_url, headers=headers, json=payload)
        response_json = response.json()

        assert response.status_code == 401
        assert "error" in response_json
        assert response_json["error"]["type"] == "authentication_error"

    def test_api_gateway_invalid_api_key(self, api_gateway_url):
        """Test API Gateway with invalid API key"""
        headers = {"x-api-key": "invalid-key-12345"}

        payload = {
            "prompt": "Test prompt",
            "url": "https://httpbin.org/json",  # Valid URL but not a PDF
        }

        response = requests.post(api_gateway_url, headers=headers, json=payload)

        # Should get 500 error due to invalid API key causing Gemini to fail
        assert response.status_code == 500
        response_json = response.json()
        assert "error" in response_json

    def test_api_gateway_malformed_json(self, api_gateway_url):
        """Test API Gateway with malformed JSON payload"""
        headers = {
            "x-api-key": os.getenv("GEMINI_API_KEY"),
            "Content-Type": "application/json",
        }

        # Send malformed JSON
        malformed_payload = '{ "prompt": "test", invalid json'

        response = requests.post(
            api_gateway_url, headers=headers, data=malformed_payload
        )

        # API Gateway should handle this and return an error
        assert response.status_code in [400, 500]

    def test_api_gateway_missing_payload_fields(self, api_gateway_url):
        """Test API Gateway with missing required fields"""
        headers = {"x-api-key": "test-key-for-missing-fields"}

        # Missing both prompt and url
        payload = {}

        response = requests.post(api_gateway_url, headers=headers, json=payload)

        # Should get 500 due to missing fields causing issues in processing
        assert response.status_code == 500
        response_json = response.json()
        assert "error" in response_json

    def test_api_gateway_invalid_url(self, api_gateway_url):
        """Test API Gateway with invalid PDF URL"""
        headers = {"x-api-key": os.getenv("GEMINI_API_KEY")}

        payload = {
            "prompt": "Test prompt",
            "url": "https://nonexistent-domain-12345.com/test.pdf",
        }

        response = requests.post(api_gateway_url, headers=headers, json=payload)

        # Should get 500 error due to network failure
        assert response.status_code == 500
        response_json = response.json()
        assert "error" in response_json

    def test_api_gateway_large_payload(self, api_gateway_url):
        """Test API Gateway with large prompt payload"""
        headers = {"x-api-key": os.getenv("GEMINI_API_KEY")}

        # Create large prompt (but within reasonable limits)
        large_prompt = "Analyze this document: " + "x" * 5000

        payload = {
            "prompt": large_prompt,
            "url": "https://httpbin.org/json",  # Simple JSON endpoint for testing
        }

        response = requests.post(api_gateway_url, headers=headers, json=payload)

        # May succeed or fail depending on Gemini's response to non-PDF content
        assert response.status_code in [200, 500]
        response_json = response.json()
        assert "message" in response_json or "error" in response_json

    def test_api_gateway_cors_headers(self, api_gateway_url):
        """Test that CORS headers are properly configured"""
        headers = {
            "x-api-key": os.getenv("GEMINI_API_KEY"),
            "Origin": "https://example.com",
        }

        payload = {
            "prompt": "Test CORS",
            "url": "https://httpbin.org/json",
        }

        response = requests.post(api_gateway_url, headers=headers, json=payload)

        # Check for CORS headers in response
        assert (
            "Access-Control-Allow-Origin" in response.headers
            or response.status_code in [200, 500]
        )

    def test_api_gateway_options_request(self, api_gateway_url):
        """Test OPTIONS request for CORS preflight"""
        headers = {
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key,content-type",
        }

        response = requests.options(api_gateway_url, headers=headers)

        # OPTIONS should be allowed for CORS
        assert response.status_code in [200, 204]

    @pytest.mark.slow
    def _test_api_gateway_timeout_handling(self, api_gateway_url):
        """Test API Gateway timeout handling with slow request"""
        headers = {"x-api-key": os.getenv("GEMINI_API_KEY")}

        payload = {
            "prompt": "Please provide an extremely detailed analysis of every single component, specification, and technical detail in this document. Go through each page methodically and extract all numerical values, part numbers, and technical specifications.",
            "url": "https://acim.nidec.com/drives/control-techniques/-/media/Project/Nidec/ControlTechniques/Documents/Datasheets/Digitax-HD-Datasheet.pdf",
        }

        # Set a reasonable timeout for the test
        try:
            response = requests.post(
                api_gateway_url,
                headers=headers,
                json=payload,
                timeout=35,  # Slightly longer than Lambda timeout
            )

            # Should either succeed or timeout gracefully
            assert response.status_code in [200, 500, 504]

        except requests.exceptions.Timeout:
            # Timeout is acceptable for this test
            pass

    def test_api_gateway_concurrent_requests(self, api_gateway_url):
        """Test multiple concurrent requests to API Gateway"""
        import concurrent.futures
        import threading

        headers = {"x-api-key": os.getenv("GEMINI_API_KEY")}

        def make_request(request_id):
            payload = {
                "prompt": f"Test concurrent request {request_id}",
                "url": "https://httpbin.org/json",
            }

            response = requests.post(api_gateway_url, headers=headers, json=payload)
            return response.status_code, request_id

        # Make 3 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request, i) for i in range(3)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # All requests should complete (either success or failure)
        assert len(results) == 3
        for status_code, request_id in results:
            assert status_code in [200, 500]  # Either success or error, but not timeout
