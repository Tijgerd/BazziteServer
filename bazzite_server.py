from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
import subprocess
import asyncio
from typing import List
import psutil

last_status = None
last_cpu_temp = None
app = FastAPI()
websocket_connections: List[WebSocket] = []

games = ["retroarch", "dolphin", "yuzu", "pcsx2", "steam"]

def detect_running_game():
    try:
        output = subprocess.check_output(["ps", "-eo", "comm"], text=True)
        for game in games:
            if game in output:
                return game
    except Exception as e:
        print(e)
    return "idle"

def get_cpu_temperature():
    try:
        temps = psutil.sensors_temperatures()
        # Prefer coretemp / Package id 0
        if "coretemp" in temps:
            for entry in temps["coretemp"]:
                if entry.label == "Package id 0" and entry.current is not None:
                    return entry.current

        # Fallback: first reasonable value
        for entries in temps.values():
            for entry in entries:
                if entry.current is not None and 0 < entry.current < 100:
                    return entry.current

    except Exception as e:
        print(e)
    return None

@app.post("/command")
async def post_command(command: dict):
    cmd = command.get("command")
    if cmd == "shutdown":
        subprocess.Popen(["systemctl", "poweroff"])
    elif cmd == "sleep":
        subprocess.Popen(["systemctl", "suspend"])
    return {"result": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global last_status, last_cpu_temp
    await websocket.accept()
    websocket_connections.append(websocket)

    # Immediately send last known values
    message = {}
    if last_status is not None:
        message["status"] = last_status
    if last_cpu_temp is not None:
        message["cpu_temperature"] = last_cpu_temp

    if message:
        await websocket.send_json(message)
        print(f"Sent initial state to new client: {message}")

    try:
        while True:
            await asyncio.sleep(1000)
    except:
        pass
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)

async def game_monitor():
    global last_status, last_cpu_temp
    first_time = True

    try:
        while True:
            status = detect_running_game()
            cpu_temp = get_cpu_temperature()

            message = {}

            # Always send first reading
            if first_time or status != last_status:
                message["status"] = status
                last_status = status
            if first_time or cpu_temp != last_cpu_temp:
                message["cpu_temperature"] = cpu_temp
                last_cpu_temp = cpu_temp

            if message and websocket_connections:
                for ws in list(websocket_connections):  # Copy to avoid modification during iteration
                    try:
                        await ws.send_json(message)
                        print(f"Sent update to clients: {message}")
                    except WebSocketDisconnect:
                        print("WebSocket disconnected, removing from list")
                        if ws in websocket_connections:
                            websocket_connections.remove(ws)
                    except Exception as e:
                        print(f"Error sending to client: {e}")
                        if ws in websocket_connections:
                            websocket_connections.remove(ws)

                first_time = False
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("game_monitor task was cancelled, exiting cleanly.")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(game_monitor())

@app.get("/")
async def root():
    return {"message": "Bazzite Server Running!"}
