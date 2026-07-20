import requests
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse, parse_qs

class DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_result = None
        self.in_title = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get('class', '')

        # Start of a new result item (the title link)
        if tag == 'a' and 'result__a' in classes:
            # If we already have a result, save it before starting a new one
            if self.current_result:
                self.results.append(self.current_result)
            
            href = attrs_dict.get('href', '')
            if 'uddg=' in href:
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                if 'uddg' in qs:
                    href = qs['uddg'][0]
            
            self.current_result = {
                "title": "",
                "url": href,
                "snippet": ""
            }
            self.in_title = True

        # Snippet link/container
        elif tag == 'a' and 'result__snippet' in classes:
            self.in_snippet = True

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_title = False
            self.in_snippet = False

    def handle_data(self, data):
        if self.in_title and self.current_result:
            self.current_result["title"] += data
        elif self.in_snippet and self.current_result:
            self.current_result["snippet"] += data

    def close(self):
        super().close()
        # Append the last result if present
        if self.current_result:
            self.results.append(self.current_result)

def search_ddg_html(query):
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    params = {"q": query}
    
    response = requests.get(url, params=params, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"HTTP error: {response.status_code}")
        
    parser = DuckDuckGoParser()
    parser.feed(response.text)
    parser.close()
    return parser.results

if __name__ == '__main__':
    try:
        results = search_ddg_html("quantum physics history")
        print(f"Success! Found {len(results)} results:")
        for r in results[:5]:
            print(f"Title: {r['title']}")
            print(f"URL: {r['url']}")
            print(f"Snippet: {r['snippet']}")
            print("-" * 30)
    except Exception as e:
        print("Failed:", e)
