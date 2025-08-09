import requests

PLAYLIST_URL = "http://onixsmart.top/get.php?username=935628344&password=778025129&type=m3u_plus&output=ts"
OUTPUT_FILE = "onixsmart_playlist.m3u"

headers = {
    "User-Agent": "VLC/3.0.20 LibVLC/3.0.20",
    "Accept": "*/*",
    "Connection": "keep-alive",
}

print(f"Downloading playlist from {PLAYLIST_URL}...")
try:
    response = requests.get(PLAYLIST_URL, headers=headers, timeout=30)
    response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

    with open(OUTPUT_FILE, "wb") as f:
        f.write(response.content)

    print(f"Playlist successfully downloaded to {OUTPUT_FILE}")

except requests.exceptions.RequestException as e:
    print(f"Error downloading playlist: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
