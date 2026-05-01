"""Unit tests for specodex.browser — HTML cleaning, JSON-LD extraction, metadata."""

from specodex.browser import (
    PageContent,
    PageMetadata,
    _extract_json_ld,
    _extract_meta,
    clean_html,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>HK-KT634WK | Mitsubishi Electric</title>
    <meta name="description" content="AC Servo Motor 400W">
    <link rel="canonical" href="https://shop.example.com/products/HK-KT634WK">
    <script type="application/ld+json">
    {
        "@type": "Product",
        "name": "HK-KT634WK",
        "sku": "HK-KT634WK",
        "offers": {"price": "450.00", "priceCurrency": "USD"}
    }
    </script>
    <script type="application/ld+json">
    {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"position": 1, "name": "Home"},
            {"position": 2, "name": "Servo Motors"},
            {"position": 3, "name": "HK-KT634WK"}
        ]
    }
    </script>
</head>
<body>
    <header><nav>Menu items here</nav></header>
    <main>
        <h1>HK-KT634WK</h1>
        <p>Rated Power: 400W</p>
        <table>
            <tr><td>Voltage</td><td>200V</td></tr>
            <tr><td>Speed</td><td>3000 rpm</td></tr>
        </table>
    </main>
    <script>var tracking = "noise";</script>
    <style>.hidden { display: none; }</style>
    <footer>Copyright 2025</footer>
    <svg><path d="M0 0"/></svg>
</body>
</html>"""


MINIMAL_HTML = "<html><body><p>Hello</p></body></html>"

HTML_NO_STRUCTURED_DATA = """<html>
<head><title>Simple Page</title></head>
<body><p>Just text</p></body>
</html>"""


# ---------------------------------------------------------------------------
# clean_html
# ---------------------------------------------------------------------------


class TestCleanHtml:
    def test_strips_script_tags(self):
        result = clean_html(SAMPLE_HTML)
        assert "tracking" not in result
        assert "noise" not in result

    def test_strips_style_tags(self):
        result = clean_html(SAMPLE_HTML)
        assert ".hidden" not in result

    def test_strips_nav_and_header(self):
        result = clean_html(SAMPLE_HTML)
        assert "Menu items" not in result

    def test_strips_footer(self):
        result = clean_html(SAMPLE_HTML)
        assert "Copyright" not in result

    def test_strips_svg(self):
        result = clean_html(SAMPLE_HTML)
        assert "path" not in result.lower() or "M0 0" not in result

    def test_preserves_content(self):
        result = clean_html(SAMPLE_HTML)
        assert "HK-KT634WK" in result
        assert "400W" in result
        assert "200V" in result
        assert "3000 rpm" in result

    def test_collapses_whitespace(self):
        html = "<p>  lots   of   space  </p>"
        result = clean_html(html)
        assert "  " not in result

    def test_truncation(self):
        long_html = "<p>" + "x" * 100_000 + "</p>"
        result = clean_html(long_html, max_chars=500)
        assert len(result) == 500

    def test_empty_input(self):
        assert clean_html("") == ""

    def test_minimal_html(self):
        result = clean_html(MINIMAL_HTML)
        assert "Hello" in result


# ---------------------------------------------------------------------------
# JSON-LD extraction
# ---------------------------------------------------------------------------


class TestExtractJsonLd:
    def test_extracts_product(self):
        results = _extract_json_ld(SAMPLE_HTML)
        types = [r.get("@type") for r in results]
        assert "Product" in types

    def test_extracts_breadcrumbs(self):
        results = _extract_json_ld(SAMPLE_HTML)
        types = [r.get("@type") for r in results]
        assert "BreadcrumbList" in types

    def test_extracts_multiple_blocks(self):
        results = _extract_json_ld(SAMPLE_HTML)
        assert len(results) == 2

    def test_no_json_ld(self):
        results = _extract_json_ld(HTML_NO_STRUCTURED_DATA)
        assert results == []

    def test_malformed_json_ld(self):
        html = '<script type="application/ld+json">{invalid json</script>'
        results = _extract_json_ld(html)
        assert results == []

    def test_json_ld_array(self):
        html = (
            '<script type="application/ld+json">[{"@type":"A"},{"@type":"B"}]</script>'
        )
        results = _extract_json_ld(html)
        assert len(results) == 2
        assert results[0]["@type"] == "A"


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


class TestExtractMeta:
    def test_title(self):
        meta = _extract_meta(SAMPLE_HTML)
        assert "HK-KT634WK" in meta.title

    def test_canonical_url(self):
        meta = _extract_meta(SAMPLE_HTML)
        assert meta.canonical_url == "https://shop.example.com/products/HK-KT634WK"

    def test_description(self):
        meta = _extract_meta(SAMPLE_HTML)
        assert meta.description == "AC Servo Motor 400W"

    def test_breadcrumbs_from_json_ld(self):
        meta = _extract_meta(SAMPLE_HTML)
        assert meta.breadcrumbs == ["Home", "Servo Motors", "HK-KT634WK"]

    def test_no_metadata(self):
        meta = _extract_meta(MINIMAL_HTML)
        assert meta.title == ""
        assert meta.canonical_url == ""
        assert meta.description == ""
        assert meta.breadcrumbs == []


# ---------------------------------------------------------------------------
# PageContent dataclass
# ---------------------------------------------------------------------------


class TestPageContent:
    def test_defaults(self):
        pc = PageContent(url="https://example.com", html="<p>test</p>")
        assert pc.structured_data == []
        assert pc.metadata.title == ""

    def test_with_metadata(self):
        meta = PageMetadata(title="Test", breadcrumbs=["A", "B"])
        pc = PageContent(url="https://example.com", html="x", metadata=meta)
        assert pc.metadata.title == "Test"
        assert pc.metadata.breadcrumbs == ["A", "B"]
