import asyncio
import time
from server import play_tamil_song

async def main():
    start_time = time.time()
    result = await play_tamil_song("Arabic Kuthu")
    end_time = time.time()
    
    print(f"Result: {result.encode('ascii', 'ignore').decode('ascii')}")
    print(f"Time Taken: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
