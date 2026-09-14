import json
import re
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


class HardwareBridge:
    def __init__(self):
        self.port: Optional[str] = None
        self.baudrate = 115200
        self.serial_conn = None
        self.thread = None
        self.running = False
        self.latest_data: Optional[Dict] = None
        self.packet_count: int = 0
        self.last_packet_time: float = 0.0

    @property
    def is_active(self) -> bool:
        return self.running and (self.latest_data is not None)

    def connect(self, port: str) -> Tuple[bool, str]:
        if not HAS_SERIAL:
            return False, "pyserial not installed"
        if self.running:
            self.disconnect()
        self.port = port
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            return True, "Connected successfully"
        except Exception as e:
            self.running = False
            return False, str(e)

    def disconnect(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.serial_conn = None

    def _read_loop(self):
        block_data = {}
        while self.running:
            try:
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue

                    # 1. JSON line: {"accel_x": 0.1, ...}
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            j = json.loads(line)
                            self.latest_data = {
                                "accelX": float(j.get("accel_x", j.get("accelX", 0.0))),
                                "accelY": float(j.get("accel_y", j.get("accelY", 0.0))),
                                "accelZ": float(j.get("accel_z", j.get("accelZ", 9.81))),
                                "gyroX": float(j.get("gyro_x", j.get("gyroX", 0.0))),
                                "gyroY": float(j.get("gyro_y", j.get("gyroY", 0.0))),
                                "gyroZ": float(j.get("gyro_z", j.get("gyroZ", 0.0))),
                                "tempC": float(j.get("mpu_temp", j.get("tempC", 26.5))),
                                "distanceMM": int(j.get("distance_mm", j.get("distanceMM", 350))),
                                "loadWeight": float(j.get("load_g", j.get("loadWeight", 0.0))),
                                "dhtTemp": j.get("dht_temp"),
                                "humidity": j.get("humidity"),
                                "mq2Raw": int(j.get("mq2_raw", 0)),
                                "gasAlarm": bool(j.get("gas_alarm", False)),
                                "rssi": -60,
                                "source": "SERIAL",
                            }
                            self.last_packet_time = time.time()
                            self.packet_count += 1
                            continue
                        except Exception:
                            pass

                    # 2. [RX] format: [RX] accelX,accelY,accelZ,gyroX,gyroY,gyroZ,tempC,distanceMM,loadWeight | RSSI: -65 dBm
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
                        continue

                    # 3. Formatted Key-Value Telemetry Block (from Serial.print in Arduino)
                    if "TELEMETRY" in line:
                        block_data = {}
                    elif "Accel" in line and ":" in line:
                        try:
                            parts = [float(x.strip()) for x in line.split(":", 1)[1].split(",")]
                            if len(parts) >= 3:
                                block_data["accelX"], block_data["accelY"], block_data["accelZ"] = parts[0], parts[1], parts[2]
                        except Exception:
                            pass
                    elif "Gyro" in line and ":" in line:
                        try:
                            parts = [float(x.strip()) for x in line.split(":", 1)[1].split(",")]
                            if len(parts) >= 3:
                                block_data["gyroX"], block_data["gyroY"], block_data["gyroZ"] = parts[0], parts[1], parts[2]
                        except Exception:
                            pass
                    elif "Distance" in line and ":" in line:
                        m = re.search(r'(-?\d+)', line.split(":", 1)[1])
                        if m: block_data["distanceMM"] = int(m.group(1))
                    elif "Load" in line and ":" in line:
                        m = re.search(r'(-?[\d\.]+)', line.split(":", 1)[1])
                        if m: block_data["loadWeight"] = float(m.group(1))
                    elif "DHT Temp" in line and ":" in line:
                        m = re.search(r'(-?[\d\.]+)', line.split(":", 1)[1])
                        if m: block_data["dhtTemp"] = float(m.group(1))
                    elif "MPU Temp" in line and ":" in line:
                        m = re.search(r'(-?[\d\.]+)', line.split(":", 1)[1])
                        if m: block_data["tempC"] = float(m.group(1))
                    elif "Humidity" in line and ":" in line:
                        m = re.search(r'(-?[\d\.]+)', line.split(":", 1)[1])
                        if m: block_data["humidity"] = float(m.group(1))
                    elif "MQ-2 Raw" in line and ":" in line:
                        m = re.search(r'(\d+)', line.split(":", 1)[1])
                        if m: block_data["mq2Raw"] = int(m.group(1))
                    elif "Gas Alarm" in line and ":" in line:
                        block_data["gasAlarm"] = "ALARM" in line.upper()
                    elif "--------" in line and block_data:
                        block_data["source"] = "SERIAL"
                        block_data["rssi"] = -60
                        if "accelX" in block_data:
                            self.latest_data = dict(block_data)
                            self.last_packet_time = time.time()
                            self.packet_count += 1
                        block_data = {}
                else:
                    time.sleep(0.05)
            except Exception:
                time.sleep(0.1)


# Global instance
bridge = HardwareBridge()


