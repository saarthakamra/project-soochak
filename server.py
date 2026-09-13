import json
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

from data_engine import MineEnvironmentSimulator, OperationalScenario
from hardware import bridge, get_available_ports

# Global simulator instance for the HTML web cockpit
sim = MineEnvironmentSimulator()
current_data = sim.step(OperationalScenario.NORMAL)
current_scenario = OperationalScenario.NORMAL


class APIHandler(SimpleHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        global current_data, sim
        if self.path == '/api/telemetry':
            hw_data = bridge.latest_data if bridge.latest_data else {
                "accelX": 0.0, "accelY": 0.0, "accelZ": 9.81,
                "gyroX": 0.0, "gyroY": 0.0, "gyroZ": 0.0,
                "tempC": 26.5, "distanceMM": 350, "loadWeight": 0.0,
                "rssi": -65
            }
            response = {
                "hardware": hw_data,
                "ports": get_available_ports(),
                "connected": bridge.running,
                "port": bridge.port
            }
            self._send_json(response)

        elif self.path == '/api/simulation/state':
            # Advance step if hardware is connected to keep simulation in sync
            if bridge.running and bridge.latest_data is not None:
                current_data = sim.step(scenario=current_scenario)

            response = {
                "step": sim.step_counter,
                "scenario": current_scenario.value,
                "threat_level": current_data["threat_level"],
                "peak_anomaly_score": current_data["peak_anomaly_score"],
                "mean_anomaly_score": current_data["mean_anomaly_score"],
                "false_alarms_rejected": current_data["false_alarms_rejected"],
                "rejection_event": current_data["rejection_event"],
                "laser_system": current_data["laser_system"],
                "nodes": current_data["nodes"],
                "history": current_data["history"][-20:],
                "logs": current_data["logs"],
                "uci_seismic": current_data.get("uci_seismic", {}),
                "insar_forecast": current_data.get("insar_forecast", {}),
                "hardware_connected": bridge.running,
                "hardware_port": bridge.port,
                "available_ports": get_available_ports(),
            }
            self._send_json(response)

        else:
            super().do_GET()

    def do_POST(self):
        global current_data, current_scenario, sim
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            req = json.loads(post_data.decode('utf-8'))
        except Exception:
            req = {}

        if self.path in ['/api/sensors', '/api/sensors/', '/api/telemetry']:
            bridge.on_wifi_data(req)
            self._send_json({"status": "ok", "received_packet": req.get("packet", bridge.packet_count)})

        elif self.path == '/api/connect':
            port = req.get('port')
            if port:
                success, msg = bridge.connect(port)
                self._send_json({"success": success, "message": msg})
            else:
                self._send_json({"success": False, "message": "Port required"}, status=400)

        elif self.path == '/api/disconnect':
            bridge.disconnect()
            self._send_json({"success": True, "message": "Disconnected"})

        elif self.path == '/api/simulation/scenario':
            sc_str = req.get('scenario', 'normal')
            scenario_map = {
                'normal': OperationalScenario.NORMAL,
                'blasting': OperationalScenario.BLASTING,
                'strata_creep': OperationalScenario.STRATA_CREEP,
                'critical_subsidence': OperationalScenario.CRITICAL_SUBSIDENCE,
                'sensor_glitch': OperationalScenario.SENSOR_GLITCH,
            }
            current_scenario = scenario_map.get(sc_str, OperationalScenario.NORMAL)
            current_data = sim.step(
                scenario=current_scenario,
                manual_disp_offset=float(req.get('manual_disp', 0.0)),
                manual_tilt_offset=float(req.get('manual_tilt', 0.0)),
                manual_laser_offset=float(req.get('manual_laser', 0.0)),
            )
            self._send_json({"success": True, "scenario": current_scenario.value})

        elif self.path == '/api/simulation/step':
            current_data = sim.step(
                scenario=current_scenario,
                manual_disp_offset=float(req.get('manual_disp', 0.0)),
                manual_tilt_offset=float(req.get('manual_tilt', 0.0)),
                manual_laser_offset=float(req.get('manual_laser', 0.0)),
            )
            self._send_json({"success": True, "step": sim.step_counter})

        elif self.path == '/api/simulation/reset':
            sim = MineEnvironmentSimulator()
            current_scenario = OperationalScenario.NORMAL
            current_data = sim.step(OperationalScenario.NORMAL)
            self._send_json({"success": True, "message": "Baseline reset"})

        else:
            self._send_json({"error": "Not Found"}, status=404)


def run(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, APIHandler)
    print(f'Starting Project Soochak Web Cockpit on http://localhost:{port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        bridge.disconnect()
        sys.exit(0)


if __name__ == '__main__':
    run()
