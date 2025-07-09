# 🎮 Bazzite Integration Server

A FastAPI server that integrates your Bazzite gaming PC with Home Assistant!

It provides:

✅ Game detection  
✅ CPU temperature monitoring  
✅ Remote shutdown & sleep commands  
✅ WebSocket-based push updates

---

## ⚡️ Quickstart (recommended)

On your Bazzite PC:

```bash
git clone https://github.com/Tijgerd/bazzite-server.git
cd bazzite-server
chmod +x install.sh
./install.sh

----

After starting, the server will listen on:
ws://YOUR-PC-IP:5000/ws
