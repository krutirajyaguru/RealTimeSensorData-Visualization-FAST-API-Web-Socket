from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketDisconnect
import pyarrow as pa
import pyarrow.ipc as ipc
import asyncio
import random
import numpy as np

app = FastAPI()

# Serve frontend
#app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


# Serve frontend ONLY under /static
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve index.html manually at root
@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

CSV_PATH = "/Users/Spiced/RealTimeSensorData/newSimpleUI/data/sensor_data.csv"

LABELS = ('x', 'y', 'z')
GROUP_SIZE = len(LABELS)
SLEEP_SEC = 0.001  # throttle for realism

# =========================
# LOAD CSV ONCE (FINITE SOURCE → UNBOUNDED REPLAY)
# =========================

csv_data = np.genfromtxt(
    CSV_PATH,
    delimiter=",",
    skip_header=1,
    dtype=np.float64,
    filling_values=0.0
)

num_cols = csv_data.shape[1]
col_names = [f"Tracker_{i}" for i in range(num_cols)]


# =========================
# STREAMING STATE (CRITICAL)
# =========================

sequence_number = 1
row_index = 0

# buffer holds exactly one logical group (x,y,z)
group_buffer = np.zeros((GROUP_SIZE, num_cols), dtype=np.float64)
'''
This client logic I have added for session:
- Backend produces data once
- Each connected client gets same frame
- No per-user computation
- A global set of connected clients

Broadcast to all of them
Now:

100 users → works

All see identical data.
'''
clients = set()

@app.websocket("/ws/stream")
async def websocket_endpoint(ws: WebSocket):

    await ws.accept()
    clients.add(ws)

    #GROUP_SIZE = 16  # number of objects per sequence
    sequence_number = 0
    row_index = 0

    try:
        while True:
        #for i in range(6):
            for row in csv_data:  # replay CSV endlessly
                group_buffer[row_index] = row

                row_index += 1

                if row_index == GROUP_SIZE:
                    
                    seq_col = np.full(num_cols, sequence_number, dtype=np.int64)
                    obj_col = np.asarray(col_names)
                    
                    x_vals = group_buffer[0]
                    y_vals = group_buffer[1]
                    z_vals = group_buffer[2]
                    print("group_buffer x:", group_buffer[0][:5])
                    print("group_buffer y:", group_buffer[1][:5])
                    print("group_buffer z:", group_buffer[2][:5])

                    table = pa.Table.from_arrays(
                        [
                            pa.array(seq_col),
                            pa.array(obj_col),
                            pa.array(x_vals),
                            pa.array(y_vals),
                            pa.array(z_vals),
                        ],
                        names=["sequence_number", "objects", "x", "y", "z"]
                    )

                    # Arrow IPC serialization
                    sink = pa.BufferOutputStream()
                    with ipc.new_stream(sink, table.schema) as writer:
                        writer.write_table(table)


                    for client in clients.copy():
                        try:
                            await client.send_bytes(sink.getvalue().to_pybytes())

                        except:
                            clients.remove(client)

                    # await ws.send_bytes(sink.getvalue().to_pybytes())
                    
                    sequence_number += 1
                    row_index = 0

                  
                    await asyncio.sleep(0.05)  # 20 Hz

    except Exception as e:
        print("WebSocket error:", e)
    except:
        clients.remove(ws)
