# Song Downloader MCP

A Model Context Protocol (MCP) server that allows searching and downloading songs from YouTube and other sources.

## Features

- **Search Songs**: Search YouTube for songs/audio matches.
- **iTunes Search**: Fetch official metadata and previews using the free iTunes Search API.
- **Tamil Song Support**: Dedicated tools for searching and downloading from `masstamilan.dev`.
- **Hyper-Optimized**: Uses persistent browser sessions and parallel processing (`asyncio.gather`) for searches, link resolution, and downloads.
- **Local Playback**: Play Tamil songs directly using VLC with automatic path discovery on Windows.
- **Trending Sync**: Automated tool (`sync_trending_hits`) that fetches Spotify's Trending Now Tamil playlist and verifies hits in parallel.
- **Download**: Download high-quality audio directly to your `downloads` folder.
- **Latest Songs**: Get trending songs for various genres.
- **List Downloads**: View files you've already downloaded.

## Installation

1. Ensure you have Python 3.10+ installed.
2. Clone or download this directory.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: This MCP uses a virtual environment internally if set up that way.)*

## Usage with Claude Desktop

Add this to your Claude Desktop configuration (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "song-downloader": {
      "command": "C:\\Users\\jeevan kishore\\.gemini\\antigravity\\scratch\\song-downloader-mcp\\venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\jeevan kishore\\.gemini\\antigravity\\scratch\\song-downloader-mcp\\server.py"]
    }
  }
}
```

## Requirements

- `yt-dlp`: For searching and downloading.
- `httpx`: For API requests.
- `mcp`: The Model Context Protocol SDK.
- `ffmpeg` (Optional): Recommended for high-quality audio conversion (e.g., to MP3). If not present, it will download in the best available native format (usually `.m4a` or `.webm`).

## Tools

- `search_songs(query, limit)`: Search YouTube.
- `search_itunes(term, limit)`: Get official metadata.
- `search_masstamilan(query)`: Search for Tamil songs/albums.
- `get_masstamilan_downloads(album_url)`: Get specific song download links from an album.
- `play_tamil_song(song_name)`: Search and play a Tamil song locally using VLC.
- `sync_trending_hits(view_threshold)`: Sync trending Spotify hits based on YouTube view counts.
- `download_song(url)`: Download audio.
- `get_latest_songs(genre)`: Fetch trending music.
- `list_downloads()`: List files in the downloads folder.
