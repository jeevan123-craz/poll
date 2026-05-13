from mcp.server.fastmcp import FastMCP
import yt_dlp
import os
import json
import asyncio
import subprocess
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
mcp = FastMCP("Song Downloader & Player")

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
SPOTIFY_TRENDING_TAMIL_ID = "37i9dQZF1DX4Im4BTs2WMg"
BASE_URL = "https://www.masstamilan.dev"
CF_IMPERSONATE = "chrome124"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# OPTIMIZATION 1: Persistent global session — warm-up happens only ONCE
# ---------------------------------------------------------------------------
_session: AsyncSession | None = None
_session_lock = asyncio.Lock()
_warmed_up = False


async def get_session() -> AsyncSession:
    global _session, _warmed_up
    async with _session_lock:
        if _session is None:
            _session = AsyncSession(impersonate=CF_IMPERSONATE)
        if not _warmed_up:
            await _session.get(BASE_URL, headers={"Referer": "https://www.google.com/"})
            _warmed_up = True
    return _session


async def cf_get(url: str, referer: str = BASE_URL) -> str:
    session = await get_session()
    resp = await session.get(url, headers={"Referer": referer})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} for {url}")
    return resp.text


async def cf_head(url: str, referer: str = BASE_URL) -> str:
    session = await get_session()
    resp = await session.head(url, headers={"Referer": referer})
    return str(resp.url)


# ---------------------------------------------------------------------------
# OPTIMIZATION 2: Resolve all redirect links in parallel
# ---------------------------------------------------------------------------
async def resolve_links_parallel(hrefs: list[str], referer: str) -> list[str]:
    async def _safe_head(href: str) -> str:
        try:
            return await cf_head(href, referer=referer)
        except Exception:
            return href
    return list(await asyncio.gather(*[_safe_head(h) for h in hrefs]))


# ---------------------------------------------------------------------------
# Tool: search_masstamilan
# ---------------------------------------------------------------------------
@mcp.tool()
async def search_masstamilan(query: str) -> str:
    """
    Search for Tamil songs on Masstamilan.dev and return album/song links.

    Args:
        query: Song or album name to search for.
    """
    search_url = f"{BASE_URL}/search?keyword={query}"
    try:
        html = await cf_get(search_url, referer=BASE_URL)
        soup = BeautifulSoup(html, "html.parser")

        results = []
        seen: set[str] = set()
        slug = query.lower().replace(" ", "-")

        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            text = a.get_text(strip=True)

            if not text or len(text) < 3:
                continue
            if not href.startswith("http"):
                href = f"{BASE_URL}{href}"
            if href in seen or BASE_URL not in href:
                continue
            if any(kw in href for kw in ["-songs", "-mp3", "-audio", slug]):
                seen.add(href)
                results.append({"title": text, "url": href})

        if not results:
            return json.dumps({
                "error": "No results matched selectors",
                "page_snippet": soup.get_text()[:2000]
            }, indent=2)

        return json.dumps(results[:10], indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ---------------------------------------------------------------------------
# Tool: get_masstamilan_downloads
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_masstamilan_downloads(album_url: str) -> str:
    """
    Get direct download links for songs from a Masstamilan album page.

    Args:
        album_url: Full URL of the Masstamilan album/song page.
    """
    try:
        html = await cf_get(album_url, referer=BASE_URL)
        soup = BeautifulSoup(html, "html.parser")

        raw: list[dict] = []

        # Masstamilan often uses a table for song listings
        # We look for rows that contain song info
        table = soup.find("table")
        if table:
            for tr in table.find_all("tr")[1:]:  # skip header
                tds = tr.find_all("td")
                if len(tds) < 2: continue
                
                title = tds[0].get_text(strip=True)
                links = tds[1].find_all("a", href=True)
                
                for a in links:
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if not href.startswith("http"): href = f"{BASE_URL}{href}"
                    
                    if "download" in href.lower() or ".mp3" in href.lower():
                        quality = "320kbps" if "320" in href or "320" in text else "128kbps"
                        raw.append({"title": title, "quality": quality, "href": href})
        
        # Fallback if no table found
        if not raw:
            for a in soup.find_all("a", href=True):
                href: str = a["href"]
                text = a.get_text(strip=True)

                if not href.startswith("http"):
                    href = f"{BASE_URL}{href}"
                
                # Filter out ZIP downloads which contain multiple songs
                if "zip" in href.lower() or "full-songs" in href.lower():
                    continue

                if not any(kw in href.lower() for kw in [".mp3", "download", "dl="]):
                    continue

                quality = "320kbps" if "320" in href or "320" in text else "128kbps"
                title = text or os.path.basename(href).replace("-", " ").replace(".mp3", "")
                raw.append({"title": title, "quality": quality, "href": href})

        if not raw:
            return json.dumps({
                "error": "No download links found",
                "page_snippet": soup.get_text()[:2000]
            }, indent=2)

        # OPTIMIZATION 3: resolve ALL redirect links in parallel
        hrefs = [r["href"] for r in raw]
        direct_urls = await resolve_links_parallel(hrefs, referer=album_url)

        songs = [
            {
                "title": r["title"],
                "quality": r["quality"],
                "direct_url": direct_urls[i],
                "original_href": r["href"],
            }
            for i, r in enumerate(raw)
        ]

        return json.dumps(songs, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ---------------------------------------------------------------------------
# Tool: play_tamil_song
# ---------------------------------------------------------------------------
@mcp.tool()
async def play_tamil_song(song_name: str) -> str:
    """
    Search Masstamilan.dev for a Tamil song and play it instantly via VLC.

    Args:
        song_name: Name of the Tamil song to play.
    """
    search_json = await search_masstamilan(song_name)
    search_results = json.loads(search_json)

    if isinstance(search_results, dict) and "error" in search_results:
        return f"Search failed: {search_results['error']}"
    if not search_results:
        return f"No results found for '{song_name}'."

    album_url = search_results[0]["url"]

    downloads_json = await get_masstamilan_downloads(album_url)
    downloads = json.loads(downloads_json)

    if isinstance(downloads, dict) and "error" in downloads:
        return f"Download fetch failed: {downloads['error']}"
    if not downloads:
        return "No playable links found."

    target = downloads[0]
    for song in downloads:
        if song_name.lower() in song["title"].lower():
            target = song
            break

    audio_url = None
    for song in [target] + downloads:
        if song.get("quality") == "320kbps":
            audio_url = song["direct_url"]
            break
    if not audio_url:
        audio_url = target["direct_url"]

    # Check common VLC paths on Windows
    vlc_cmd = "vlc"
    common_paths = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
    ]
    
    if subprocess.run(["where", "vlc"], capture_output=True).returncode != 0:
        for path in common_paths:
            if os.path.exists(path):
                vlc_cmd = path
                break

    # Stop any existing VLC instances to prevent parallel playback
    subprocess.run(["taskkill", "/F", "/IM", "vlc.exe"], capture_output=True)

    try:
        # Start VLC with HTTP interface enabled for remote control
        subprocess.Popen(
            [vlc_cmd, "--intf", "dummy", "--extraintf", "http", "--http-password", "mcp", "--http-port", "8080", "--play-and-exit", audio_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return (
            f"🎶 Now playing: {target['title']}\n"
            f"Album: {search_results[0]['title']}\n"
            f"Quality: {target['quality']}\n"
            f"Source: Masstamilan"
        )
    except Exception as e:
        return f"Error playing song: {e}. Please install VLC or add it to your PATH."


# ---------------------------------------------------------------------------
# Tool: download_song
# ---------------------------------------------------------------------------
@mcp.tool()
async def download_song(url: str) -> str:
    """
    Download audio from a URL (YouTube, direct MP3, etc.).

    Args:
        url: Direct MP3 link or any yt-dlp-compatible URL.
    """
    if url.split("?")[0].lower().endswith(".mp3"):
        filename = os.path.basename(url.split("?")[0]) or "download.mp3"
        path = os.path.join(DOWNLOAD_DIR, filename)
        try:
            session = await get_session()          # reuse shared session
            resp = await session.get(url, headers={"Referer": BASE_URL})
            with open(path, "wb") as f:
                f.write(resp.content)
            return f"✅ Downloaded: {filename}\nSaved to: {path}"
        except Exception as e:
            return f"Error downloading MP3: {e}"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "concurrent_fragment_downloads": 4,    # OPTIMIZATION 4: parallel fragments
    }

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    try:
        loop = asyncio.get_running_loop()       # OPTIMIZATION 5: faster loop access
        filename = await loop.run_in_executor(None, _download)

        if not os.path.exists(filename):
            base = os.path.splitext(filename)[0]
            candidates = [
                f for f in os.listdir(DOWNLOAD_DIR)
                if f.startswith(os.path.basename(base))
            ]
            filename = os.path.join(DOWNLOAD_DIR, candidates[0]) if candidates else filename

        return f"✅ Downloaded: {os.path.basename(filename)}\nSaved to: {filename}"
    except Exception as e:
        return f"Error downloading via yt-dlp: {e}"


# ---------------------------------------------------------------------------
# Tool: search_songs
# ---------------------------------------------------------------------------
@mcp.tool()
async def search_songs(query: str, limit: int = 5) -> str:
    """
    Search for songs on YouTube and return a list of matches.

    Args:
        query: Search term.
        limit: Max number of results (default 5).
    """
    ydl_opts = {"noplaylist": True, "quiet": True, "extract_flat": True}

    def _search():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, _search)

        results = [
            {
                "title": e.get("title"),
                "url": f"https://www.youtube.com/watch?v={e.get('id')}",
                "duration": e.get("duration"),
                "uploader": e.get("uploader"),
            }
            for e in info.get("entries", [])
        ]
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching YouTube: {e}"


# ---------------------------------------------------------------------------
# Tool: search_itunes
# ---------------------------------------------------------------------------
@mcp.tool()
async def search_itunes(term: str, limit: int = 10) -> str:
    """
    Search for official song metadata using the iTunes Search API (free, no key).

    Args:
        term: Song/artist name.
        limit: Max results (default 10).
    """
    url = f"https://itunes.apple.com/search?term={term}&media=music&limit={limit}"
    try:
        session = await get_session()
        resp = await session.get(url)
        data = resp.json()

        results = [
            {
                "trackName": i.get("trackName"),
                "artistName": i.get("artistName"),
                "collectionName": i.get("collectionName"),
                "previewUrl": i.get("previewUrl"),
                "trackViewUrl": i.get("trackViewUrl"),
                "releaseDate": i.get("releaseDate"),
            }
            for i in data.get("results", [])
        ]
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching iTunes: {e}"


# ---------------------------------------------------------------------------
# Tool: sync_trending_hits
# ---------------------------------------------------------------------------
@mcp.tool()
async def sync_trending_hits(view_threshold: int = 50_000_000) -> str:
    """
    Automated workflow:
    1. Extracts 'Trending Now Tamil' playlist from Spotify.
    2. Verifies YouTube views for each track (in parallel).
    3. Downloads tracks with > threshold views (default 50M).

    Args:
        view_threshold: Minimum view count to trigger download.
    """
    playlist_url = f"https://open.spotify.com/playlist/{SPOTIFY_TRENDING_TAMIL_ID}"
    ydl_opts = {"extract_flat": True, "quiet": True}

    def _get_tracks():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(playlist_url, download=False)

    def _get_yt_info(title: str):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{title} official video", download=False)
            entries = info.get("entries", [])
            return entries[0] if entries else None

    try:
        loop = asyncio.get_running_loop()
        playlist_info = await loop.run_in_executor(None, _get_tracks)

        if "entries" not in playlist_info:
            return "Could not extract tracks from the Spotify playlist."

        titles = [e.get("title", "Unknown") for e in playlist_info["entries"]]

        # OPTIMIZATION 6: fetch all YouTube view counts in parallel
        yt_infos = await asyncio.gather(
            *[loop.run_in_executor(None, _get_yt_info, t) for t in titles]
        )

        results = []
        downloaded = skipped = 0

        for title, video_info in zip(titles, yt_infos):
            if not video_info:
                results.append(f"❌ {title} — not found on YouTube")
                continue

            views = video_info.get("view_count", 0)
            if views > view_threshold:
                await download_song(video_info["webpage_url"])
                results.append(f"✅ {title} ({views:,} views) — DOWNLOADED")
                downloaded += 1
            else:
                results.append(f"⏩ {title} ({views:,} views) — SKIPPED")
                skipped += 1

        summary = f"\n📊 Summary: {downloaded} downloaded, {skipped} skipped."
        return "\n".join(results) + summary

    except Exception as e:
        return f"Error in sync workflow: {e}"


# ---------------------------------------------------------------------------
# Tool: get_spotify_trending_tracks
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_spotify_trending_tracks() -> str:
    """
    Get the list of tracks from the 'Trending Now Tamil' Spotify playlist.
    """
    playlist_url = f"https://open.spotify.com/playlist/{SPOTIFY_TRENDING_TAMIL_ID}"
    ydl_opts = {"extract_flat": True, "quiet": True}

    def _get_tracks():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(playlist_url, download=False)

    try:
        loop = asyncio.get_running_loop()
        playlist_info = await loop.run_in_executor(None, _get_tracks)
        
        tracks = [
            {
                "title": e.get("title", "Unknown"),
                "url": e.get("url"),
                "id": e.get("id")
            }
            for e in playlist_info.get("entries", [])
        ]
        return json.dumps(tracks, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ---------------------------------------------------------------------------
# Tool: get_latest_songs
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_latest_songs(genre: str = "trending") -> str:
    """
    Get the latest trending songs for a specific genre.

    Args:
        genre: Music genre or mood (default 'trending').
    """
    return await search_songs(f"latest {genre} songs 2025 official music video", limit=10)


# ---------------------------------------------------------------------------
# Tool: list_downloads
# ---------------------------------------------------------------------------
@mcp.tool()
async def list_downloads() -> str:
    """List all songs saved in the local downloads folder."""
    try:
        files = os.listdir(DOWNLOAD_DIR)
        if not files:
            return "No downloads found."
        return "\n".join(f"- {f}" for f in sorted(files))
    except Exception as e:
        return f"Error listing downloads: {e}"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
