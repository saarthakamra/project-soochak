import http.server
import json
import math
import re
import socket
import socketserver
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def get_available_ports() -> List[str]:
    if not HAS_SERIAL:
        return []
    return [port.device for port in serial.tools.list_ports.comports()]


def get_local_wifi_ips() -> List[str]:
    """Discover all local IPv4 addresses on laptop to assist Wi-Fi AP pairing."""
    ips = []
    try:
        out = subprocess.check_output(["ifconfig"], text=True, stderr=subprocess.DEVNULL)
        found = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out)
        for ip in found:
            if ip != "127.0.0.1" and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            ips.append("192.168.4.2")
    return ips


class SensorHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Lightweight HTTP server receiving telemetry POSTs from ESP32 in Wi-Fi AP Mode."""
    
    def _set_cors_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_cors_headers(200)

    def do_POST(self):
        # Support /api/sensors (default in ESP32 code) and /api/telemetry
        if self.path in ['/api/sensors', '/api/sensors/', '/api/telemetry', '/api/telemetry/']:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                data = json.loads(body.decode('utf-8'))
                bridge.on_wifi_data(data)
                self._set_cors_headers(200)
                resp = {
                    "status": "ok",
                    "received_packet": data.get("packet", bridge.packet_count),
                    "node_id": "S-103",
                    "timestamp": time.time()
                }
                self.wfile.write(json.dumps(resp).encode('utf-8'))
            except Exception as e:
                self._set_cors_headers(400)
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        self._set_cors_headers(200)
        status_payload = {
            "service": "Project Soochak Wi-Fi Sensor Receiver",
            "active": bridge.is_active,
            "connection_type": bridge.connection_type,
            "packets_received": bridge.packet_count,
            "last_seen_seconds_ago": round(time.time() - bridge.last_packet_time, 1) if bridge.last_packet_time else None,
            "ap_ssid_expected": "SOOCHAK_NODE",
            "esp32_ip_expected": "192.168.4.1",
            "local_ips": get_local_wifi_ips(),
            "latest_data": bridge.latest_data
        }
        self.wfile.write(json.dumps(status_payload, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging to console
        pass


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class HardwareBridge:
    def __init__(self):
        self.port: Optional[str] = None
        self.baudrate = 115200
        self.serial_conn = None
        self.serial_thread = None
        self.running = False

        # Wi-Fi AP Mode state
        self.connection_type: Optional[str] = None  # 'WIFI_AP' | 'SERIAL' | None
        self.packet_count: int = 0
        self.last_packet_time: float = 0.0
        self.http_server: Optional[ThreadedTCPServer] = None
        self.http_thread: Optional[threading.Thread] = None
        self.http_port: int = 3000

        self.latest_data: Optional[Dict] = None

    @property
    def is_active(self) -> bool:
        """Returns True if live hardware is actively transmitting data within timeout."""
        if self.connection_type == "WIFI_AP":
            return (self.latest_data is not None) and ((time.time() - self.last_packet_time) < 8.0)
        elif self.connection_type == "SERIAL":
            return self.running and (self.latest_data is not None)
        return False

    def on_wifi_data(self, raw_json: Dict):
        """Ingest and normalize JSON telemetry payload sent by ESP32 via HTTP POST."""
        self.packet_count += 1
        self.last_packet_time = time.time()
        self.connection_type = "WIFI_AP"
        self.running = True

        # Normalize keys (handle both snake_case from Arduino and camelCase)
        normalized = {
            "accelX": float(raw_json.get("accel_x", raw_json.get("accelX", 0.0))),
            "accelY": float(raw_json.get("accel_y", raw_json.get("accelY", 0.0))),
            "accelZ": float(raw_json.get("accel_z", raw_json.get("accelZ", 9.81))),
            "gyroX": float(raw_json.get("gyro_x", raw_json.get("gyroX", 0.0))),
            "gyroY": float(raw_json.get("gyro_y", raw_json.get("gyroY", 0.0))),
            "gyroZ": float(raw_json.get("gyro_z", raw_json.get("gyroZ", 0.0))),
            "tempC": float(raw_json.get("mpu_temp", raw_json.get("tempC", 25.0))),
            "distanceMM": int(raw_json.get("distance_mm", raw_json.get("distanceMM", 0))),
            "loadWeight": float(raw_json.get("load_g", raw_json.get("loadWeight", 0.0))),
            "dhtTemp": raw_json.get("dht_temp"),
            "humidity": raw_json.get("humidity"),
            "mq2Raw": int(raw_json.get("mq2_raw", 0)),
            "gasAlarm": bool(raw_json.get("gas_alarm", False)),
            "packet": int(raw_json.get("packet", self.packet_count)),
            "source": "WIFI_AP",
            "rssi": -50,  # strong direct AP signal
            "timestamp": self.last_packet_time,
        }
        self.latest_data = normalized

    def start_wifi_receiver(self, port: int = 3000):
        """Start the background HTTP server listening for ESP32 POST requests."""
        if self.http_server is not None:
            return  # already running
        
        self.http_port = port
        try:
            self.http_server = ThreadedTCPServer(('0.0.0.0', self.http_port), SensorHTTPHandler)
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()
            print(f"[HardwareBridge] Wi-Fi AP Ingestion Server listening on http://0.0.0.0:{self.http_port}/api/sensors")
        except OSError as e:
            print(f"[HardwareBridge] Port {port} already bound or busy: {e}")

    def connect(self, port: str) -> Tuple[bool, str]:
        """Connect to hardware over USB Serial."""
        if not HAS_SERIAL:
            return False, "pyserial not installed"
        if self.running and self.connection_type == "SERIAL":
            self.disconnect()
        self.port = port
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            self.connection_type = "SERIAL"
            self.serial_thread = threading.Thread(target=self._serial_read_loop, daemon=True)
            self.serial_thread.start()
            return True, "Connected successfully via USB Serial"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        """Disconnect USB Serial connection."""
        self.running = False
        if self.connection_type == "SERIAL":
            self.connection_type = None
        if self.serial_thread:
            self.serial_thread.join(timeout=1.0)
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

    def _serial_read_loop(self):
        while self.running and self.connection_type == "SERIAL":
            try:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line.startswith("[RX]"):
                        parts = line.split("|")
                        if len(parts) >= 1:
                            csv_part = parts[0].replace("[RX]", "").strip()
                            vals = csv_part.split(",")
                            if len(vals) >= 9:
                                data = {
                                    "accelX": float(vals[0]),
                                    "accelY": float(vals[1]),
                                    "accelZ": float(vals[2]),
                                    "gyroX": float(vals[3]),
                                    "gyroY": float(vals[4]),
                                    "gyroZ": float(vals[5]),
                                    "tempC": float(vals[6]),
                                    "distanceMM": float(vals[7]),
                                    "loadWeight": float(vals[8]),
                                    "rssi": -65,
                                    "source": "SERIAL",
                                }
                                if len(parts) >= 2 and "RSSI:" in parts[1]:
                                    rssi_match = re.search(r"RSSI:\s*(-?\d+)", parts[1])
                                    if rssi_match:
                                        data["rssi"] = int(rssi_match.group(1))
                                self.latest_data = data
                                self.last_packet_time = time.time()
                                self.packet_count += 1
            except Exception:
                time.sleep(0.1)


# Global instance & auto-start Wi-Fi listener
bridge = HardwareBridge()
bridge.start_wifi_receiver(3000)

