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

def detect_steam_game_via_local_api():
    try:
        resp = requests.get('http://localhost:27060/clients/status.json', timeout=1)
        data = resp.json()
        players = data.get('players', [])
        if players:
            gameid = players[0].get('gameid')
            if gameid and gameid != "0":
                return gameid
    except Exception as e:
        print(f"Error querying Steam local API: {e}")
    return None

def get_app_name_from_steam_api(appid):
    if appid in appid_cache:
        return appid_cache[appid]
    try:
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
        resp = requests.get(url, timeout=2)
        data = resp.json()
        app_data = data.get(str(appid), {})
        if app_data.get('success') and 'data' in app_data:
            name = app_data['data'].get('name')
            if name:
                appid_cache[appid] = name
                return name
    except Exception as e:
        print(f"Error querying Steam Web API: {e}")
    return f"SteamApp {appid}"

def detect_running_game_process():
    try:
        # Get all processes
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] == 'steam':
                steam_pid = proc.info['pid']
                break
        else:
            steam_pid = None

        # If Steam is running, check its children
        if steam_pid:
            steam_proc = psutil.Process(steam_pid)
            children = steam_proc.children(recursive=True)
            for child in children:
                name = child.name().lower()
                if name not in ["steamwebhelper", "steam"]:
                    return name

            # Fallback if only Steam is found
            return "steam"

        # Otherwise check for known emulators
        for proc in psutil.process_iter(['name']):
            name = proc.info['name'].lower()
            if name in ["retroarch", "dolphin", "yuzu", "pcsx2"]:
                return name

    except Exception as e:
        print(e)

    return "idle"

def detect_running_game():
    # First try Steam local API
    appid = detect_steam_game_via_local_api()
    if appid:
        name = get_app_name_from_steam_api(appid)
        return name

    # Fallback
    return detect_running_game_process()

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
