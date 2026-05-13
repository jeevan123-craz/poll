import asyncio
import server
import json

async def test_links():
    album_url = "https://www.masstamilan.dev/vikram-songs"
    print(f"Fetching links for {album_url}...")
    try:
        res = await server.get_masstamilan_downloads(album_url)
        data = json.loads(res)
        print("Download Links found:")
        for item in data:
            print(f"- {item['title']} ({item['quality']}): {item['direct_url']}")
            
        if data:
            print("\nTesting first link download...")
            dl_res = await server.download_song(data[0]['direct_url'])
            print(dl_res)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_links())
