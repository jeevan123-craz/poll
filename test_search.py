import asyncio
import server
import json

async def test_search():
    print("Testing Masstamilan search...")
    try:
        res = await server.search_masstamilan("Vikram")
        print("Masstamilan Results:")
        print(res)
    except Exception as e:
        print(f"Masstamilan Error: {e}")

    print("\nTesting YouTube search...")
    try:
        res = await server.search_songs("Vikram")
        print("YouTube Results:")
        print(res)
    except Exception as e:
        print(f"YouTube Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
