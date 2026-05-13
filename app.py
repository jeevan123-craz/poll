from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import server
import json
import os
import httpx
import subprocess
import psutil

app = FastAPI(title="Tamil Song Hub API")

@app.get("/")
async def get_ui():
    return FileResponse("index.html")

@app.get("/favicon.ico")
async def favicon():
    return ""

# Enable CORS for local UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str

class DownloadRequest(BaseModel):
    url: str

@app.get("/search/masstamilan")
async def search_masstamilan(query: str):
    res = await server.search_masstamilan(query)
    data = json.loads(res)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data

@app.get("/search/youtube")
async def search_youtube(query: str):
    res = await server.search_songs(query)
    return json.loads(res)

@app.get("/album/downloads")
async def get_downloads(url: str):
    res = await server.get_masstamilan_downloads(url)
    data = json.loads(res)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data

@app.post("/play")
async def play_song(request: SearchRequest):
    res = await server.play_tamil_song(request.query)
    return {"message": res}

@app.post("/download")
async def download_song(request: DownloadRequest):
    res = await server.download_song(request.url)
    return {"message": res}

@app.post("/sync-trending")
async def sync_trending(threshold: int = 50000000):
    res = await server.sync_trending_hits(threshold)
    return {"message": res}

@app.get("/list-downloads")
async def list_downloads():
    res = await server.list_downloads()
    return {"files": res.split("\n") if res != "No downloads found." else []}

@app.get("/spotify/trending")
async def spotify_trending():
    res = await server.get_spotify_trending_tracks()
    data = json.loads(res)
    if isinstance(data, dict) and "error" in data:
        raise HTTPException(status_code=502, detail=data["error"])
    return data

@app.get("/itunes/search")
async def itunes_search(term: str, limit: int = 10):
    res = await server.search_itunes(term, limit)
    return json.loads(res)

@app.get("/latest")
async def latest_songs(genre: str = "trending"):
    res = await server.get_latest_songs(genre)
    return json.loads(res)

@app.get("/trending")
async def get_trending():
    # Spotify uses DRM — return curated Tamil trending hits
    return [
        {"title": "Arabic Kuthu", "artist": "Anirudh Ravichander"},
        {"title": "Kaavaalaa", "artist": "Anirudh Ravichander"},
        {"title": "Jigidi Killaadi", "artist": "Anirudh"},
        {"title": "Vaathi Coming", "artist": "Anirudh Ravichander"},
        {"title": "Chellamma", "artist": "Anirudh Ravichander"},
        {"title": "Pathala Pathala", "artist": "Anirudh Ravichander"},
        {"title": "Rowdy Baby", "artist": "Yuvan Shankar Raja"},
        {"title": "Kannaana Kanney", "artist": "D. Imman"},
        {"title": "Beast Mode", "artist": "Anirudh Ravichander"},
        {"title": "Butta Bomma Tamil", "artist": "Armaan Malik"},
        {"title": "Naacho Naacho Tamil", "artist": "SS Thaman"},
        {"title": "Surviva", "artist": "Anirudh Ravichander"},
    ]

@app.get("/player/status")
async def get_player_status():
    """Check VLC state via its HTTP API."""
    try:
        async with httpx.AsyncClient(auth=("", "mcp")) as client:
            resp = await client.get("http://localhost:8080/requests/status.json", timeout=1.0)
            if resp.status_code != 200:
                return {"state": "stopped", "title": "Nothing playing", "progress": 0}
            
            data = resp.json()
            state = data.get("state", "stopped")
            
            # Extract title from metadata if available
            info = data.get("information", {}).get("category", {}).get("meta", {})
            title = info.get("title") or info.get("filename")
            
            if not title:
                # Fallback: extract from URI
                uri = data.get("stats", {}).get("inputuri", "")
                if uri:
                    title = uri.split('/')[-1].split('?')[0].replace('%20', ' ')
            
            # Calculate progress
            time = data.get("time", 0)
            length = data.get("length", 0)
            progress = (time / length * 100) if length > 0 else 0
            
            return {
                "state": "playing" if state == "playing" else "paused" if state == "paused" else "stopped",
                "title": title or "Streaming…",
                "progress": progress
            }
    except Exception:
        return {"state": "stopped", "title": "Nothing playing", "progress": 0}

@app.post("/player/pause")
async def pause_vlc():
    """Toggle pause/resume via VLC HTTP API."""
    try:
        async with httpx.AsyncClient(auth=("", "mcp")) as client:
            resp = await client.get("http://localhost:8080/requests/status.json?command=pl_pause", timeout=2.0)
            if resp.status_code == 200:
                return {"status": "toggled"}
            raise HTTPException(status_code=resp.status_code, detail="VLC API error")
    except Exception as e:
        # Fallback to psutil if HTTP fails (process might be suspended)
        procs = [p for p in psutil.process_iter(['name','status']) if p.info['name'] and 'vlc' in p.info['name'].lower()]
        if procs:
            for p in procs:
                if p.status() == psutil.STATUS_STOPPED: p.resume()
                else: p.suspend()
            return {"status": "toggled (process level)"}
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/player/stop")
async def stop_vlc():
    """Kill VLC and clear status."""
    try:
        # Try graceful stop first
        async with httpx.AsyncClient(auth=("", "mcp")) as client:
            await client.get("http://localhost:8080/requests/status.json?command=pl_stop", timeout=1.0)
        
        # Then kill process to be sure
        subprocess.run(["taskkill", "/F", "/IM", "vlc.exe"], capture_output=True)
        return {"status": "stopped"}
    except Exception:
        # Fallback to direct kill
        subprocess.run(["taskkill", "/F", "/IM", "vlc.exe"], capture_output=True)
        return {"status": "stopped"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
