import requests
from bs4 import BeautifulSoup

def fetch_html(url):
    # Standard headers to mimic a real browser visit
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    try:
        # 1. Send a GET request to the URL
        response = requests.get(url, headers=headers, timeout=10)
        
        # 2. Check if the request was successful (Status Code 200)
        response.raise_for_status()
        
        # 3. Parse the content with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 4. Return the prettified HTML
        return soup.prettify()

    except requests.exceptions.HTTPError as errh:
        return f"HTTP Error: {errh}"
    except requests.exceptions.ConnectionError as errc:
        return f"Error Connecting: {errc}"
    except requests.exceptions.Timeout as errt:
        return f"Timeout Error: {errt}"
    except requests.exceptions.RequestException as err:
        return f"Oops: Something Else {err}"

# Example usage:
target_url = "https://www.example.com"
html_content = fetch_html(target_url)

# Save to a file or print
with open("output.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("HTML fetched and saved to output.html")