import asyncio
import server
import os

async def test_download():
    print("Testing MP3 download...")
    url = "https://cdn.masstamilan.dev/songs/vikram/Vikram-Title-Track.mp3"
    # Actually masstamilan links might need a referer or they might be redirected.
    # Let's try a direct download via server.download_song
    try:
        res = await server.download_song(url)
        print(res)
        # Check if file exists
        filename = "Vikram-Title-Track.mp3"
        path = os.path.join(server.DOWNLOAD_DIR, filename)
        if os.path.exists(path):
            print(f"File downloaded successfully to {path}")
            # Clean up
            os.remove(path)
        else:
            print(f"File NOT found at {path}")
    except Exception as e:
        print(f"Download Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_download())
