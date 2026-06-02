"""
MediaFire downloader — merges both provided scripts:
  • Script 1  → Selenium-based direct-link extractor  (single file, GUI version)
  • Script 2  → requests + gazpacho bulk folder downloader (CLI version)

Public API
----------
get_file_info(url)          -> dict  {filename, size, size_mb, hash, link, owner, privacy, type}
get_folder_files(folder_key)-> list  [ {filename, size, size_mb, hash, link}, ... ]
download_file(url, dest_dir, progress_cb) -> str  (local file path)
"""

import asyncio
import base64
import hashlib
import http.client
import os
import re
import urllib.parse
from gzip import GzipFile
from io import BytesIO

import aiohttp
import aiofiles
from bs4 import BeautifulSoup

from config import Config

# ── Constants ──────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
        "Gecko/20100101 Firefox/131.0"
    ),
    "Accept-Encoding": "gzip",
}

NON_ALPHANUM = "-_. "
NON_ALPHANUM_REPLACEMENT = "-"


# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    return "".join(
        c if (c.isalnum() or c in NON_ALPHANUM) else NON_ALPHANUM_REPLACEMENT
        for c in name
    )


def _api_folder_endpoint(folder_key: str, chunk: int = 1, content_type: str = "files") -> str:
    return (
        f"https://www.mediafire.com/api/1.4/folder/get_content.php"
        f"?r=utga&content_type={content_type}&filter=all"
        f"&order_by=name&order_direction=asc&chunk={chunk}"
        f"&version=1.5&folder_key={folder_key}&response_format=json"
    )


def _api_folder_info_endpoint(folder_key: str) -> str:
    return (
        f"https://www.mediafire.com/api/1.4/folder/get_info.php"
        f"?r=utga&content_type=folder&filter=all&order_by=name"
        f"&order_direction=asc&chunk=1&version=1.5"
        f"&folder_key={folder_key}&response_format=json"
    )


def _api_file_info_endpoint(file_key: str) -> str:
    return (
        f"https://www.mediafire.com/api/file/get_info.php"
        f"?quick_key={file_key}&response_format=json"
    )


# ── Direct-link extractor (from Script 1 logic, no Selenium — pure HTTP) ──────

def _extract_direct_link_from_html(html: str, original_url: str) -> str | None:
    """Parse MediaFire page HTML to find the direct download URL."""

    # 1. File-ID based regex (most reliable)
    id_match = re.search(r"/file/([a-zA-Z0-9]+)/", original_url)
    if id_match:
        fid = re.escape(id_match.group(1))
        m = re.search(
            r"https?://download\d*\.mediafire\.com/[^\"']*?" + fid + r"/[^\"']+",
            html, re.IGNORECASE,
        )
        if m:
            return m.group(0)

    # 2. data-scrambled-url attribute (Script 2 logic)
    try:
        soup = BeautifulSoup(html, "html.parser")
        btn  = soup.find("a", {"id": "downloadButton"})
        if btn and btn.get("data-scrambled-url"):
            return base64.b64decode(btn["data-scrambled-url"]).decode()
    except Exception:
        pass

    # 3. JavaScript variable download_link
    m = re.search(
        r'(?:var|const|let)\s+download_link\s*=\s*[\'"]'
        r'(https?://(?:www\.)?mediafire\.com/download[^"\']*)[\'"]',
        html,
    )
    if m:
        return m.group(1)

    # 4. Broad download subdomain regex
    m = re.search(r"https?://download\d*\.mediafire\.com/[^\s\"']+", html)
    if m:
        return m.group(0)

    return None


def _fetch_direct_link_sync(page_url: str) -> str | None:
    """Synchronous HTTP fetch of MediaFire page then extract direct link."""
    parsed = urllib.parse.urlparse(page_url)
    conn   = http.client.HTTPSConnection(parsed.netloc, timeout=30)
    path   = parsed.path
    if parsed.query:
        path += "?" + parsed.query
    conn.request("GET", path, headers=HEADERS)
    resp = conn.getresponse()

    encoding = resp.getheader("Content-Encoding", "")
    raw = resp.read()
    conn.close()

    if encoding == "gzip":
        with GzipFile(fileobj=BytesIO(raw)) as f:
            html = f.read().decode("utf-8", errors="replace")
    else:
        html = raw.decode("utf-8", errors="replace")

    return _extract_direct_link_from_html(html, page_url)


# ── Async public API ───────────────────────────────────────────────────────────

async def get_file_info(url: str) -> dict:
    """
    Accepts a MediaFire file page URL (including dkey/r query params).
    Returns dict with filename, size_mb, hash, link, owner, privacy, type.
    """
    # Strip query string first, then extract key
    # Handles:
    #   /file/y55w43577s2388c/filename/file?dkey=...
    #   /file/y55w43577s2388c/filename/file
    #   /file/y55w43577s2388c
    clean_url = url.split("?")[0].rstrip("/")
    m = re.search(r"mediafire\.com/(?:file|file_premium)/([a-zA-Z0-9]+)", clean_url)
    if not m:
        raise ValueError("Invalid MediaFire file URL")
    file_key = m.group(1)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(_api_file_info_endpoint(file_key)) as resp:
            data = await resp.json(content_type=None)

    if data["response"]["result"] != "Success":
        raise ValueError(data["response"].get("message", "MediaFire API error"))

    info = data["response"]["file_info"]
    size = int(info.get("size", 0))
    return {
        "filename": info.get("filename", "file"),
        "size":     size,
        "size_mb":  round(size / 1024 / 1024, 2),
        "hash":     info.get("hash", ""),
        "link":     info["links"]["normal_download"],
        "owner":    info.get("owner_name", "Unknown"),
        "privacy":  info.get("privacy", "public"),
        "type":     info.get("filetype", ""),
        "file_key": file_key,
    }


async def get_folder_info(folder_key: str) -> dict:
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(_api_folder_info_endpoint(folder_key)) as resp:
            data = await resp.json(content_type=None)
    if data["response"]["result"] != "Success":
        raise ValueError(data["response"].get("message", "Folder not found"))
    return data["response"]["folder_info"]


async def get_folder_files(folder_key: str) -> list[dict]:
    """
    Recursively collects ALL files inside a MediaFire folder (and sub-folders).
    Returns a flat list of file-info dicts.
    """
    all_files = []
    await _collect_files_recursive(folder_key, all_files)
    return all_files


async def _collect_files_recursive(folder_key: str, bucket: list):
    # --- files in this folder ---
    chunk, more = 1, True
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        while more:
            async with session.get(_api_folder_endpoint(folder_key, chunk, "files")) as r:
                data = await r.json(content_type=None)
            fc = data["response"].get("folder_content", {})
            for f in fc.get("files", []):
                size = int(f.get("size", 0))
                bucket.append({
                    "filename": f.get("filename", "file"),
                    "size":     size,
                    "size_mb":  round(size / 1024 / 1024, 2),
                    "hash":     f.get("hash", ""),
                    "link":     f["links"]["normal_download"],
                })
            more  = fc.get("more_chunks") == "yes"
            chunk += 1

    # --- sub-folders ---
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(_api_folder_endpoint(folder_key, 1, "folders")) as r:
            data = await r.json(content_type=None)
    fc = data["response"].get("folder_content", {})
    for sub in fc.get("folders", []):
        await _collect_files_recursive(sub["folderkey"], bucket)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


async def download_file(
    download_url: str,
    dest_dir: str,
    filename: str,
    expected_hash: str = "",
    progress_cb=None,          # async callable(downloaded_bytes, total_bytes)
) -> str:
    """
    Downloads a file from download_url into dest_dir/filename.
    Handles MediaFire redirect pages (gzip HTML with data-scrambled-url).
    Calls progress_cb(downloaded, total) periodically.
    Returns local file path.
    """
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, normalize_name(filename))

    # Skip if already downloaded and hash matches
    if os.path.exists(dest) and expected_hash:
        if _sha256(dest) == expected_hash:
            return dest

    # --- resolve actual download URL (may be a redirect HTML page) ---
    actual_url = await _resolve_download_url(download_url)

    # --- stream download ---
    async with aiohttp.ClientSession(headers={
        "User-Agent": HEADERS["User-Agent"],
        "Referer": "https://www.mediafire.com/",
    }) as session:
        async with session.get(actual_url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            last_cb = 0

            async with aiofiles.open(dest, "wb") as f:
                async for chunk in resp.content.iter_chunked(Config.CHUNK_SIZE):
                    await f.write(chunk)
                    downloaded += len(chunk)
                    # throttle callbacks to every ~0.5 s worth of data
                    if progress_cb and (downloaded - last_cb) >= Config.CHUNK_SIZE * 4:
                        await progress_cb(downloaded, total)
                        last_cb = downloaded

            if progress_cb:
                await progress_cb(downloaded, total)

    return dest


async def _resolve_download_url(url: str) -> str:
    """
    If url is a MediaFire file-page URL (not a direct cdn link),
    fetch the page and extract the real cdn link.
    """
    if "download" in url and "mediafire.com" not in url.split("/")[2].lstrip("download"):
        return url  # already a CDN link
    if re.match(r"https?://download\d*\.mediafire\.com/", url):
        return url  # direct CDN

    # It's a normal_download page URL — fetch it
    loop = asyncio.get_running_loop()
    direct = await loop.run_in_executor(None, _fetch_direct_link_sync, url)
    if direct:
        return direct

    # Fallback: try following redirects via aiohttp
    async with aiohttp.ClientSession(headers=HEADERS, max_redirects=10) as session:
        async with session.get(url, allow_redirects=True) as resp:
            final_url = str(resp.url)
            if "download" in final_url:
                return final_url
            # Page returned HTML — parse it
            html = await resp.text(errors="replace")
            direct = _extract_direct_link_from_html(html, url)
            if direct:
                return direct

    raise ValueError(f"Could not resolve direct download link for: {url}")
