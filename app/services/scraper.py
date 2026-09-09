import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup


MAX_RESPONSE_BYTES = 2_000_000
MAX_TEXT_LENGTH = 15_000
UNWANTED_TAGS = ["script", "style", "nav", "header", "footer", "aside", "noscript", "svg", "form"]


class InvalidUrlError(Exception):
    pass


class DisallowedHostError(Exception):
    pass


class ScrapeError(Exception):
    pass


def _is_disallowed_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


async def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InvalidUrlError

    try:
        addresses = await _resolve_host(parsed.hostname)
    except socket.gaierror as error:
        raise ScrapeError from error

    if not addresses or any(_is_disallowed_address(address) for address in addresses):
        raise DisallowedHostError


async def _resolve_host(hostname: str) -> set[str]:
    try:
        ipaddress.ip_address(hostname)
        return {hostname}
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    results = await loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    return {result[4][0] for result in results}


def _extract_text(html: bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(UNWANTED_TAGS):
        tag.decompose()

    text = "\n".join(line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip())
    if len(text) < 50:
        raise ScrapeError
    return _truncate(text)


def _truncate(text: str) -> str:
    if len(text) <= MAX_TEXT_LENGTH:
        return text

    cutoff = max(
        (index for index, character in enumerate(text[: MAX_TEXT_LENGTH + 1]) if character.isspace()),
        default=-1,
    )
    return text[:cutoff] if cutoff > 0 else text[:MAX_TEXT_LENGTH]


async def scrape_url(url: str) -> str:
    await validate_url(url)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TailorDocs/1.0)"}

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False, headers=headers) as client:
            async with client.stream("GET", url) as response:
                if not response.is_success or "text/html" not in response.headers.get("content-type", "").lower():
                    raise ScrapeError
                if int(response.headers.get("content-length", "0")) > MAX_RESPONSE_BYTES:
                    raise ScrapeError

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        # A partial HTML document can produce misleading extracted text.
                        raise ScrapeError
    except (httpx.HTTPError, ValueError) as error:
        raise ScrapeError from error

    if not body:
        raise ScrapeError
    return _extract_text(bytes(body))
