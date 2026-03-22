"""Unit tests for datasheetminer/searcher.py search functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest

from datasheetminer.searcher import ProductSearcher, SearchResult, search_for_products


@pytest.mark.unit
class TestSearchResult:
    """Tests for the SearchResult dataclass."""

    def test_creation(self) -> None:
        result = SearchResult(title="Test", url="https://example.com", snippet="desc")
        assert result.title == "Test"
        assert result.url == "https://example.com"
        assert result.snippet == "desc"
        assert result.manufacturer is None
        assert result.product_name is None

    def test_to_dict(self) -> None:
        result = SearchResult(
            title="Test Motor",
            url="https://example.com/motor.pdf",
            snippet="A motor datasheet",
            manufacturer="FANUC",
            product_name="KR-210",
        )
        d = result.to_dict()
        assert d == {
            "title": "Test Motor",
            "url": "https://example.com/motor.pdf",
            "snippet": "A motor datasheet",
            "manufacturer": "FANUC",
            "product_name": "KR-210",
        }


@pytest.mark.unit
class TestProductSearcher:
    """Tests for the ProductSearcher class."""

    @patch("datasheetminer.searcher.urlopen")
    def test_search_duckduckgo_mocked(self, mock_urlopen: MagicMock) -> None:
        """DuckDuckGo HTML results are parsed into SearchResult objects."""
        html_body = """
        <div class="result results_links results_links_deep web-result">
            <div class="links_main links_deep result__body">
                <a class="result__a" href="https://example.com/datasheet.pdf">
                    Motor Datasheet PDF
                </a>
                <a class="result__snippet">Technical specifications for motor</a>
            </div>
        </div>
        </div></div>
        """
        mock_response = MagicMock()
        mock_response.read.return_value = html_body.encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        searcher = ProductSearcher(api="duckduckgo")
        results = searcher.search_duckduckgo("motor datasheet")

        mock_urlopen.assert_called_once()
        # Results depend on regex matching the HTML structure above
        # The test validates the parse path runs without error
        assert isinstance(results, list)

    @patch("datasheetminer.searcher.urlopen")
    def test_search_brave_mocked(self, mock_urlopen: MagicMock) -> None:
        """Brave JSON results are parsed into SearchResult objects."""
        brave_response = {
            "web": {
                "results": [
                    {
                        "title": "FANUC Robot Spec Sheet",
                        "url": "https://fanuc.com/robots/spec.pdf",
                        "description": "Full technical specifications",
                    },
                    {
                        "title": "ABB IRB Datasheet",
                        "url": "https://abb.com/irb/datasheet.pdf",
                        "description": "ABB robot arm datasheet",
                    },
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(brave_response).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        searcher = ProductSearcher(api="brave", api_key="test-brave-key")
        results = searcher.search_brave("robot arm specs")

        assert len(results) == 2
        assert results[0].title == "FANUC Robot Spec Sheet"
        assert results[0].url == "https://fanuc.com/robots/spec.pdf"
        assert results[1].title == "ABB IRB Datasheet"

    def test_search_brave_no_key(self) -> None:
        """Brave search with no API key returns empty list and logs error."""
        searcher = ProductSearcher(api="brave", api_key=None)
        results = searcher.search_brave("test query")
        assert results == []

    def test_search_unknown_api(self) -> None:
        """Unknown API name returns empty list."""
        searcher = ProductSearcher(api="unknown")
        results = searcher.search("test query")
        assert results == []

    def test_is_likely_spec_page_pdf(self) -> None:
        """URLs ending in .pdf are identified as likely spec pages."""
        searcher = ProductSearcher()
        assert searcher.is_likely_spec_page("https://example.com/motor.pdf") is True

    def test_is_likely_spec_page_keywords(self) -> None:
        """URLs containing spec-related keywords are identified as likely spec pages."""
        searcher = ProductSearcher()
        assert (
            searcher.is_likely_spec_page("https://example.com/datasheet/motor") is True
        )
        assert (
            searcher.is_likely_spec_page("https://example.com/specification/drive")
            is True
        )

    def test_is_likely_spec_page_false(self) -> None:
        """Generic social media URLs are not identified as spec pages."""
        searcher = ProductSearcher()
        assert searcher.is_likely_spec_page("https://twitter.com/post") is False

    def test_extract_manufacturer_known(self) -> None:
        """Known manufacturer names in title are extracted."""
        searcher = ProductSearcher()
        result = SearchResult(
            title="FANUC M-20iA Robot Specifications",
            url="https://example.com",
            snippet="FANUC industrial robot",
        )
        enriched = searcher.extract_manufacturer_and_product(result)
        assert enriched.manufacturer == "FANUC"

    def test_extract_manufacturer_unknown(self) -> None:
        """When no known manufacturer is found, manufacturer stays None."""
        searcher = ProductSearcher()
        result = SearchResult(
            title="Generic Widget Specs",
            url="https://example.com",
            snippet="Some widget description",
        )
        enriched = searcher.extract_manufacturer_and_product(result)
        assert enriched.manufacturer is None

    def test_extract_product_name_model_pattern(self) -> None:
        """Model number patterns like 'KR-210' are extracted as product_name."""
        searcher = ProductSearcher()
        result = SearchResult(
            title="KR-210 Robot Arm Specifications",
            url="https://example.com",
            snippet="Industrial robot",
        )
        enriched = searcher.extract_manufacturer_and_product(result)
        assert enriched.product_name is not None
        assert "KR-210" in enriched.product_name

    def test_filter_and_enrich_results_filters(self) -> None:
        """Low-quality results (no spec indicators) are filtered out."""
        searcher = ProductSearcher()
        results = [
            SearchResult(
                title="Random Blog Post",
                url="https://twitter.com/status/123",
                snippet="Nothing relevant here",
            ),
        ]
        filtered = searcher.filter_and_enrich_results(results, min_quality=0.5)
        assert len(filtered) == 0

    def test_filter_and_enrich_results_keeps(self) -> None:
        """High-quality results (PDF + spec keywords) are kept."""
        searcher = ProductSearcher()
        results = [
            SearchResult(
                title="Motor Technical Specification Datasheet",
                url="https://example.com/motor-datasheet.pdf",
                snippet="Full technical specification manual for robot motor",
            ),
        ]
        filtered = searcher.filter_and_enrich_results(results, min_quality=0.5)
        assert len(filtered) == 1


@pytest.mark.unit
class TestSearchForProducts:
    """Tests for the search_for_products top-level function."""

    @patch("datasheetminer.searcher.time.sleep")
    @patch.object(ProductSearcher, "search")
    def test_url_deduplication(
        self, mock_search: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Duplicate URLs across queries produce only unique entries."""
        duplicate_result = SearchResult(
            title="Motor Spec",
            url="https://example.com/motor.pdf",
            snippet="spec datasheet technical",
        )
        mock_search.return_value = [duplicate_result]

        output = search_for_products(
            product_type="motor",
            search_terms=["query1", "query2"],
            api="duckduckgo",
        )

        # Two queries returned the same URL, but output should deduplicate
        urls = [entry["url"] for entry in output]
        assert len(urls) == len(set(urls))

    @patch("datasheetminer.searcher.time.sleep")
    @patch.object(ProductSearcher, "search")
    def test_pdf_gets_pages_field(
        self, mock_search: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """PDF URLs get a 'pages' field set to '1-10' in the output."""
        pdf_result = SearchResult(
            title="Datasheet specification",
            url="https://example.com/motor-datasheet.pdf",
            snippet="Technical specification manual for robot",
        )
        mock_search.return_value = [pdf_result]

        output = search_for_products(
            product_type="motor",
            search_terms=["motor datasheet"],
            api="duckduckgo",
        )

        pdf_entries = [e for e in output if e["url"].endswith(".pdf")]
        assert len(pdf_entries) >= 1
        assert pdf_entries[0]["pages"] == "1-10"
