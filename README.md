# Real-Time 3D Streaming with FastAPI, Apache Arrow & Plotly
## Overview

### This project streams real-time 3D position data (16 objects) from a backend to a browser using:
- FastAPI (Python backend)
- WebSockets (real-time communication)
- Apache Arrow (IPC format) (binary serialization)
- Plotly.js (3D visualization in browser, 16 objects - live)

The goal is to achieve high-performance, low-latency real-time visualization without JSON overhead.

## Architecture
    FastAPI Backend
        │
        │  Arrow IPC (binary)
        ▼
    WebSocket Connection
        ▼
    Browser Frontend
        │
        │  Apache Arrow JS parses binary
        ▼
    Plotly 3D Visualization

## Data Structure Transformation

### Original data was wide format (16 columns):
    +-----------+-----------+-----------+ ... +------------+
    | Tracker0  | Tracker1  | Tracker2  | ... | Tracker15  |
    +-----------+-----------+-----------+ ... +------------+
    | 0.32      | 0.55      | 0.35      | ... | 0.71       | ---> x_values
    +-----------+-----------+-----------+ ... +------------+
    | 0.16      | 0.57      | 0.33      | ... | 0.47       | ---> y_values
    +-----------+-----------+-----------+ ... +------------+
    | 0.12      | 0.955     | 0.33      | ... | 0.73       | ---> z_values
    +-----------+-----------+-----------+ ... +------------+
### Converted to Long (Normalized) Format

    Transformed it into following columns:

    +-----------+-------+-------+-------+-------------------+
    | objects   |   x   |   y   |   z   | sequence_number   | 
    +-----------+-------+-------+-------+-------------------|
    |     0     | 0.12  | 0.44  | 0.88  |  1                |
    |     1     | 0.55  | 0.11  | 0.72  |  1                |
    |   ...     |  ...  |  ...  |  ...  |  ...              |
    |    15     | 0.77  | 0.61  | 0.09  |  1                |
    +-------------------------------------------------------+ 
        

### Why Conversion is Good for Streaming

#### Long format benefits real-time systems:
- Single schema
- Easier filtering
- Simple IPC serialization
- Works well with Arrow columnar layout
- Frontend can plot by grouping on object_id

## Data Flow Explanation
### Backend:

- Generate 16 random 3D points.
- Convert to Apache Arrow Table.
- Serialize using IPC stream format.
- Send binary data via WebSocket.

## Project Structure

    project/
    │
    │── frontend/
    │   └── index.html 
    ├── main.py                # FastAPI backend
    │
    ├── frontend/
    │   └── index.html         # Frontend page
    │
    └── README.md


## Setup

```bash
python3 -m venv newvenv
source newvenv/bin/activate
pip install --upgrade pip

pip install fastapi uvicorn pyarrow numpy

uvicorn main:app --reload
```

### Server runs at:

    http://127.0.0.1:8000


### Frontend:

- Receive ArrayBuffer.
- Convert to Arrow Table using tableFromIPC.
- Extract x, y, z columns.
- Update Plotly 3D scatter plot.

## Arrow is ideal for:

- Real-time streaming
- Numerical datasets
- High-frequency updates

## FastAPI + WebSocket + Arrow Debug Notes

---

### 1. FastAPI WebSocket 404 + Unsupported Upgrade Error

```
INFO:     127.0.0.1:54552 - "GET /ws/stream HTTP/1.1" 404 Not Found
WARNING:  Unsupported upgrade request.
WARNING:  No supported WebSocket library detected.
Please use "pip install 'uvicorn[standard]'",
or install 'websockets' or 'wsproto' manually.
```
---

#### What Happened

Uvicorn was installed **without WebSocket support**.

By default:

```
pip install uvicorn
```

does NOT install the required WebSocket libraries.

So when the browser tries to upgrade:

```
GET /ws/stream
```

The upgrade fails → 404 + unsupported upgrade warning.

---

#### Solution

Install Uvicorn with WebSocket extras:

```bash
pip install "uvicorn[standard]"
```

OR install the WebSocket libraries manually:

```bash
pip install websockets wsproto
```
---
#### Restart Server

After installing, restart:

```bash
uvicorn main:app --reload
```

If your file is named `backend.py`, use:

```bash
uvicorn backend:app --reload
```

---
#### Rule to Remember

> `uvicorn` alone does NOT include WebSocket support.  
> Always use:
>
> ```bash
> pip install "uvicorn[standard]"
> ```

when working with FastAPI WebSockets.

### 2. FastAPI Crash

#### Error

```
AssertionError: scope["type"] == "http"
```

#### What Happened

A WebSocket request was routed to `StaticFiles`.

`StaticFiles` only supports **HTTP**, not **WebSockets**.

#### Root Cause

`StaticFiles` was mounted at `/`, which captured the WebSocket route (`/ws/stream`) before FastAPI’s WebSocket router could handle it.

#### Wrong Pattern

```python
app.mount("/", StaticFiles(directory="frontend"), name="static")
```

#### Correct Pattern

```python
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    ...
```

#### Rule to Remember

> Never mount `StaticFiles` at `/` when using WebSockets.  
> Always mount static files on a subpath like `/static`.

---

### 3. Blank Browser Page

#### How to Open DevTools

**Mac:**  
`Cmd + Option + I`

**Windows / Linux:**  
`Ctrl + Shift + I`

Or:

Right-click → **Inspect** → **Console**

---

#### What to Check

##### Console Tab
- `console.log(...)` output
- JavaScript errors

Quick test:

```javascript
console.log("DevTools working");
```

##### Network Tab
- Filter by **WS**
- Click `/ws/stream`
- Verify frames are coming in

---

### 4. JavaScript Error

#### Error

```
Uncaught ReferenceError: arrow is not defined
```

#### Cause

The Apache Arrow CDN does **not** expose a global `arrow` object.

This breaks:

```javascript
arrow.Table.from(...)
```

JavaScript crashes before Plotly updates → page appears blank.

---

### 5. Arrow Fix

#### Wrong

```javascript
const table = await arrow.Table.from(event.data);
```

#### Correct IPC API

```javascript
const table = Arrow.tableFromIPC(new Uint8Array(event.data));
```

- No `await`
- No `arrow.` namespace

---

### 6. Chrome Specific Issue

#### Error

```
ReferenceError: apacheArrow / Arrow is not defined
```

Even when script is included.

#### Likely Cause

MIME type / `nosniff` issue from CDN.

#### Fix Options

- Serve the UMD bundle locally
- Or switch to ES module import

Safari may appear to work even with broken MIME types, but Chrome will fail.

---

### 7. Final Working Solution Used

Instead of using the Arrow JS API directly:

```javascript
aq.fromArrow(...)
```

Arquero correctly handled the Arrow IPC data and avoided the global namespace issue.

---

## Key Debug Rule

> If WebSocket connects but page is blank →  
> Always check the browser Console first.  
> A single JavaScript error can silently stop rendering.