from ddgs import DDGS

try:
    with DDGS() as ddgs:
        res = list(ddgs.text("quantum physics history", max_results=5))
        print("Success! Results list size:", len(res))
        for r in res:
            print("Title:", r.get("title"))
            print("Link:", r.get("href"))
            print("Body:", r.get("body")[:100] + "...")
            print("-" * 20)
except Exception as e:
    print(f"Failed with exception: {e}")
