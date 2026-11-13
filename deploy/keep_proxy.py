"""Use the server's existing Mihomo; start it after reboot if absent."""
import socket,subprocess,time
while True:
    try:
        with socket.create_connection(('127.0.0.1',7890),timeout=2):pass
    except OSError:
        process=subprocess.Popen(['/usr/local/bin/mihomo','-d','/root/.config/mihomo','-ext-ctl','127.0.0.1:9090'])
        raise SystemExit(process.wait())
    time.sleep(10)
