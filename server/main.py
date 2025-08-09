import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import m3u8
import os

app = FastAPI()
log = logging.getLogger("uvicorn.error")

playlist_data: list["PlaylistItem"] = []

class PlaylistItem(BaseModel):
    title: str
    uri: str

def parse_ip_tv_m3u(text: str) -> list[PlaylistItem]:
    items: list[PlaylistItem] = []
    pending_title: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            comma = line.rfind(",")
            title = line[comma+1:].strip() if comma != -1 else "Untitled"
            pending_title = title or "Untitled"
        elif line.startswith("#"):
            continue
        else:
            if pending_title:
                items.append(PlaylistItem(title=pending_title, uri=line))
                pending_title = None
    return items

def parse_hls(text: str) -> list[PlaylistItem]:
    items: list[PlaylistItem] = []
    obj = m3u8.loads(text)
    if obj.is_variant:
        for i, pl in enumerate(obj.playlists, 1):
            attrs = []
            if pl.stream_info and pl.stream_info.bandwidth:
                attrs.append(f"{pl.stream_info.bandwidth//1000}kbps")
            if pl.stream_info and pl.stream_info.resolution:
                w, h = pl.stream_info.resolution
                attrs.append(f"{w}x{h}")
            title = " / ".join(attrs) or f"Variant {i}"
            items.append(PlaylistItem(title=title, uri=pl.uri))
    else:
        for i, seg in enumerate(obj.segments, 1):
            title = seg.title or f"Segment {i}"
            items.append(PlaylistItem(title=title, uri=seg.uri))
    return items

def fetch_and_parse(url: str) -> list[PlaylistItem]:
    raw_content: bytes
    content_type: str = "" # Initialize content_type for local files

    if url.startswith("file://"):
        file_path = url[len("file://"):]
        # Ensure the path is absolute and correctly formatted for the OS
        if not os.path.isabs(file_path):
            # Assuming the file is in the project root if relative path is given
            file_path = os.path.join(os.getcwd(), file_path) # This might be wrong, as server/main.py is in server/
            # Better: assume file_path is relative to the server directory, or provide full path.
            # For now, let's assume the user provides the full absolute path.
            # The user downloaded it to C:\roku\playlist_manager\onixsmart_playlist.m3u
            # So the path should be absolute.
            pass # file_path is already absolute from the user's input

        try:
            with open(file_path, "rb") as f:
                raw_content = f.read()
            log.info(f"Read playlist from local file: {file_path}")
            content_type = "application/x-mpegURL" # Default for M3U
        except FileNotFoundError:
            raise ValueError(f"Local playlist file not found: {file_path}")
        except Exception as e:
            raise ValueError(f"Error reading local playlist file {file_path}: {e}")
    else:
        headers = {
            # multe portaluri IPTV blochează agenți necunoscuți
            "User-Agent": "VLC/3.0.20 LibVLC/3.0.20",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        raw_content = r.content
        content_type = r.headers.get("Content-Type", "")
        log.info(f"Fetched playlist from URL: {url}")

    # decodare robustă la BOM/charset-uri neanunțate
    text: str
    for enc in ("utf-8-sig", "utf-8", "iso-8859-1"): # Removed r.encoding as it's not always present
        try:
            text = raw_content.decode(enc)
            break
        except Exception:
            continue
    else:
        text = raw_content.decode("utf-8", errors="ignore") # ultim fallback

    # sanity check minim
    if b"<html" in raw_content.lower() or "text/html" in content_type.lower():
        snippet = raw_content[:300].decode("utf-8", errors="ignore")
        raise ValueError(f"Server returned HTML, not M3U. Content-Type={content_type}; head={snippet!r}")

    if "#EXTM3U" not in text:
        head = text[:300].replace("\r", "\\r").replace("\n", "\\n")
        raise ValueError(f"Not an M3U playlist (missing #EXTM3U). Head={head!r}")

    # HLS sau IPTV clasic?
    if "#EXTINF:" in text:
        items = parse_ip_tv_m3u(text)
    elif "#EXT-X-" in text:
        items = parse_hls(text)
    else:
        # If neither specific tag is found, but it's an M3U, default to IPTV M3U parsing
        if "#EXTM3U" in text:
            items = parse_ip_tv_m3u(text)
        else:
            raise ValueError(f"Could not determine playlist type (HLS or IPTV M3U). Missing #EXTM3U, #EXTINF:, or #EXT-X-.")

    return items


PLAYLIST_URL = "file://C:/roku/playlist_manager/onixsmart_playlist.m3u"
# PLAYLIST_URL = "https://iptv-org.github.io/iptv/countries/us.m3u"

@app.on_event("startup")
def load_playlist():
    try:
        items = fetch_and_parse(PLAYLIST_URL)
        playlist_data.clear()
        playlist_data.extend(items)
        log.info("Loaded %d playlist items.", len(playlist_data))
    except Exception as e:
        # NU mai oprim aplicația. Logăm și lăsăm endpointul /reload să fie folosit manual.
        log.error("Playlist load failed: %s", e)
        playlist_data.clear()

@app.post("/reload")
def reload():
    try:
        items = fetch_and_parse(PLAYLIST_URL)
        playlist_data.clear()
        playlist_data.extend(items)
        return {"status": "ok", "count": len(playlist_data)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/playlist", response_model=list[PlaylistItem])
def get_playlist(page: int = 1, size: int = 50):
    if page < 1 or size < 1:
        raise HTTPException(status_code=400, detail="page and size must be positive integers")
    start = (page - 1) * size
    end = start + size
    return playlist_data[start:end]
