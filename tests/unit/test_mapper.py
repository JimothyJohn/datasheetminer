"""Unit tests for specodex/mapper.py."""

from unittest.mock import MagicMock, patch

import pytest

from specodex.mapper import find_manufacturers, results_to_manufacturers
from specodex.models.manufacturer import Manufacturer


@pytest.mark.unit
class TestFindManufacturers:
    """Tests for find_manufacturers()."""

    @patch("specodex.mapper.build")
    def test_success(self, mock_build: MagicMock) -> None:
        """API returns items -- function returns list with one dict."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.cse.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "title": "ABB",
                    "link": "https://abb.com",
                    "snippet": "ABB is a global leader",
                },
            ]
        }

        results = find_manufacturers("industrial motors", api_key="fake-key")

        assert len(results) == 1
        assert results[0]["title"] == "ABB"
        assert results[0]["link"] == "https://abb.com"
        assert results[0]["snippet"] == "ABB is a global leader"
        mock_build.assert_called_once_with(
            "customsearch", "v1", developerKey="fake-key"
        )

    @patch("specodex.mapper.build")
    def test_api_error(self, mock_build: MagicMock) -> None:
        """build() raises an exception -- returns empty list."""
        mock_build.side_effect = Exception("API quota exceeded")

        results = find_manufacturers("motors", api_key="fake-key")

        assert results == []

    @patch("specodex.mapper.build")
    def test_limit_respected(self, mock_build: MagicMock) -> None:
        """Only limit number of results returned even when API returns more."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.cse.return_value.list.return_value.execute.return_value = {
            "items": [
                {"title": f"Mfg{i}", "link": f"https://mfg{i}.com", "snippet": ""}
                for i in range(10)
            ]
        }

        results = find_manufacturers("motors", api_key="fake-key", limit=2)

        assert len(results) == 2


@pytest.mark.unit
class TestResultsToManufacturers:
    """Tests for results_to_manufacturers()."""

    def test_conversion(self) -> None:
        """Dict with title and link converts to Manufacturer model."""
        results = [{"title": "ABB", "link": "https://abb.com"}]

        manufacturers = results_to_manufacturers(results)

        assert len(manufacturers) == 1
        assert isinstance(manufacturers[0], Manufacturer)
        assert manufacturers[0].name == "ABB"
        assert manufacturers[0].website == "https://abb.com"

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        manufacturers = results_to_manufacturers([])

        assert manufacturers == []

    def test_missing_fields(self) -> None:
        """Dict missing 'link' key results in website=None."""
        results = [{"title": "Test"}]

        manufacturers = results_to_manufacturers(results)

        assert len(manufacturers) == 1
        assert manufacturers[0].name == "Test"
        assert manufacturers[0].website is None
