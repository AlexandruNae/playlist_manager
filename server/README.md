# Playlist Manager Server

This server fetches a large M3U playlist, parses it, and provides a paginated API for the Roku application.

## Setup

1.  **Install Python 3.7+**

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Server

```bash
uvicorn main:app --reload
```

The server will be running at `http://127.0.0.1:8000`.

## API Endpoints

*   `GET /playlist`: Returns a paginated list of playlist items.
    *   Query Parameters:
        *   `page` (int, optional, default: 1): The page number to retrieve.
        *   `size` (int, optional, default: 50): The number of items per page.
