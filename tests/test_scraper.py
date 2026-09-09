import pytest

from app.services.scraper import DisallowedHostError, MAX_TEXT_LENGTH, ScrapeError, _extract_text, validate_url


def test_extracts_visible_text_and_removes_unwanted_tags():
    html = b"""
    <html><body>
      <header>Header text that must not be included in the candidate.</header>
      <main><h1>Backend Engineer</h1><p>Build reliable APIs for customers and improve service performance.</p></main>
      <script>Hidden script text that must not be included in the candidate.</script>
      <style>Hidden style text that must not be included in the candidate.</style>
      <nav>Navigation text that must not be included in the candidate.</nav>
      <footer>Footer text that must not be included in the candidate.</footer>
      <aside>Aside text that must not be included in the candidate.</aside>
      <noscript>Noscript text that must not be included in the candidate.</noscript>
      <svg>SVG text that must not be included in the candidate.</svg>
      <form>Form text that must not be included in the candidate.</form>
    </body></html>
    """

    text = _extract_text(html)

    assert text == "Backend Engineer\nBuild reliable APIs for customers and improve service performance."


def test_truncates_scraped_text_at_whitespace():
    text = _extract_text(f"<p>{'word ' * 4_000}</p>".encode())

    assert len(text) <= MAX_TEXT_LENGTH
    assert not text.endswith(" ")


def test_rejects_short_extracted_text():
    with pytest.raises(ScrapeError):
        _extract_text(b"<p>Too short</p>")


@pytest.mark.asyncio
async def test_rejects_loopback_url_before_request():
    with pytest.raises(DisallowedHostError):
        await validate_url("http://127.0.0.1")
