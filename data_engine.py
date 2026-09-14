"""
Project Soochak - Mine Assessment & Terrain Response
Smart India Hackathon 2026 | Problem Statement 26025
Team MATR

data_engine.py:
- Synthetic sensor data engine simulating distributed ESP32 mesh nodes
- Hardware payload: MPU6050 (tilt/vibration), VL53L1X (laser ToF displacement),
  HX711 + Load Cell (strata load), BME280/DS18B20 (environmental), MQ-4 (methane)
- Independent Long-Baseline Laser Reference System (500m+ optical path)
- Isolation Forest ML model for multi-sensor anomaly detection
- Multi-node spatial correlation & false-alarm rejection engine
"""

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from hardware import bridge
from models.seismic_isolation_forest import get_seismic_detector
from models.stgcn_lstm import get_stgcn_forecaster
from data.insar_india_dataset import load_insar_spatial_data


class OperationalScenario(str, Enum):
    NORMAL = "normal"
    BLASTING = "blasting"  # Transient shockwave, high vibration, 0 displacement -> False Alarm Rejection
    STRATA_CREEP = "strata_creep"  # Progressive micro-deformation, slow tilt & displacement rise -> Warning
    CRITICAL_SUBSIDENCE = "critical_subsidence"  # Severe multi-node coordinated displacement & laser shift -> Critical
    SENSOR_GLITCH = "sensor_glitch"  # Single node erratic drift, no neighbor confirmation -> Suppressed


class ThreatLevel(str, Enum):
    SAFE = "SAFE"
    WATCH = "WATCH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class SensorNode:
    node_id: str
    name: str
    lat: float
    lon: float
    depth_m: float
    panel_zone: str
    base_load_kN: float = 140.0
    battery_pct: float = 95.0
    rssi_dbm: int = -65

    # Telemetry (Hardware Stack: MPU6050, VL53L1X, HX711, BME280, DS18B20, MQ-4)
    pitch_deg: float = 0.12          # MPU6050
    roll_deg: float = 0.08           # MPU6050
    tilt_magnitude_deg: float = 0.14 # sqrt(pitch^2 + roll^2)
    vibration_rms_g: float = 0.04   # MPU6050 acceleration RMS
    vibration_peak_g: float = 0.08  # MPU6050 peak g
    displacement_mm: float = 0.3    # VL53L1X ToF / crack opening
    displacement_rate_mm_min: float = 0.0
    load_kN: float = 140.0          # Load Cell + HX711 prop pressure
    load_delta_kN: float = 0.0      # Load deviation from calibrated baseline
    temp_c: float = 26.5            # BME280 / DS18B20
    humidity_pct: float = 68.0      # BME280
    pressure_hpa: float = 1012.5    # BME280
    methane_ppm: float = 160.0      # MQ-4 sensor

    # ML Anomaly Scoring
    anomaly_score: float = 0.03
    status: str = "SAFE"
    last_updated: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LaserReferenceSystem:
    tx_name: str = "Laser Transmitter Tx-1 (North Portal)"
    tx_lat: float = 23.7538
    tx_lon: float = 86.4150
    rx_name: str = "Detector Plate Rx-1 (Tailgate Hub)"
    rx_lat: float = 23.7505
    rx_lon: float = 86.4245
    baseline_meters: float = 980.0
    spot_x_mm: float = 0.04
    spot_y_mm: float = -0.06
    total_deviation_mm: float = 0.07
    intensity_pct: float = 97.2
    snr_db: float = 38.5
    calibrated: bool = True
    status: str = "ALIGNED"

    def update_deviation(self, dx: float, dy: float, intensity_noise: float = 0.0):
        self.spot_x_mm = round(dx, 3)
        self.spot_y_mm = round(dy, 3)
        self.total_deviation_mm = round(math.sqrt(dx**2 + dy**2), 3)
        self.intensity_pct = round(max(10.0, min(100.0, 97.2 - self.total_deviation_mm * 4.0 + intensity_noise)), 1)
        if self.total_deviation_mm > 2.5:
            self.status = "CRITICAL_DEVIATION"
        elif self.total_deviation_mm > 0.8:
            self.status = "WARNING_DEVIATION"
        elif self.total_deviation_mm > 0.3:
            self.status = "WATCH_DRIFT"
        else:
            self.status = "ALIGNED"


class SubsidenceAnomalyDetector:
    """
    Isolation Forest ML Engine for Mine Subsidence Detection.
    - Learns multivariate normal behavior from tilt, vibration, displacement, load delta, and laser deviation.
    - Employs spatial neighborhood correlation to cross-validate alerts and reject false alarms.
    """

    FEATURE_NAMES = [
        "tilt_magnitude_deg",
        "vibration_rms_g",
        "vibration_peak_g",
        "displacement_mm",
        "displacement_rate_mm_min",
        "load_delta_kN",
        "laser_deviation_mm",
        "spatial_discrepancy_mm",
    ]

    def __init__(self, n_estimators: int = 120, contamination: float = 0.02, random_state: int = 42):
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.is_trained = False

    def extract_feature_vector(self, node: SensorNode, laser_dev_mm: float, spatial_discrepancy: float) -> np.ndarray:
        return np.array([
            node.tilt_magnitude_deg,
            node.vibration_rms_g,
            node.vibration_peak_g,
            node.displacement_mm,
            node.displacement_rate_mm_min,
            node.load_delta_kN,
            laser_dev_mm,
            spatial_discrepancy,
        ], dtype=float)

    def fit(self, baseline_df: pd.DataFrame):
        """Fit scaler and Isolation Forest model on normal operating baseline data."""
        X = baseline_df[self.FEATURE_NAMES].values
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.is_trained = True

    def compute_anomaly_score(self, feature_vector: np.ndarray) -> float:
        """
        Compute continuous anomaly score between 0.0 (Normal) and 1.0 (Critical).
        """
        if not self.is_trained:
            norm_disp = min(1.0, feature_vector[3] / 5.0)
            norm_tilt = min(1.0, feature_vector[0] / 3.0)
            return round(0.5 * norm_disp + 0.5 * norm_tilt, 3)

        scaled = self.scaler.transform(feature_vector.reshape(1, -1))
        raw_score = float(self.model.decision_function(scaled)[0])

        k = (-0.01 - raw_score) / 0.045
        anomaly_score = 1.0 / (1.0 + math.exp(-2.2 * k))
        return round(float(np.clip(anomaly_score, 0.02, 0.98)), 3)


class MineEnvironmentSimulator:
    """
    Simulates distributed multi-sensor IoT network for Jharia Coalfield Panel 4-B.
    Coordinates: ~23.75° N, 86.42° E.
    Simulates:
    - 8 ESP32 sensor nodes covering longwall panel, goaf margins, village zone, and railway.
    - Long-baseline laser reference optical array.
    - Operational scenarios with multi-node spatial correlation.
    """

    def __init__(self):
        self.laser_system = LaserReferenceSystem(
            tx_name="Laser Transmitter Tx-1 (North Portal)",
            tx_lat=23.7538,
            tx_lon=86.4150,
            rx_name="Detector Plate Rx-1 (Tailgate Hub)",
            rx_lat=23.7505,
            rx_lon=86.4245,
            baseline_meters=980.0,
        )

        self.initial_nodes_config = [
            {
                "id": "S-101",
                "name": "Entry Gate Drift Node",
                "lat": 23.7535,
                "lon": 86.4162,
                "depth_m": 180,
                "panel_zone": "Panel 4-B North Barrier",
                "base_load": 142.0,
                "base_temp": 26.4,
                "base_methane": 165.0,
            },
            {
                "id": "S-102",
                "name": "Goaf Perimeter Node A",
                "lat": 23.7526,
                "lon": 86.4179,
                "depth_m": 185,
                "panel_zone": "Panel 4-B Goaf Margin West",
                "base_load": 180.0,
                "base_temp": 27.1,
                "base_methane": 195.0,
            },
            {
                "id": "S-103",
                "name": "Longwall Face Center Node",
                "lat": 23.7518,
                "lon": 86.4196,
                "depth_m": 185,
                "panel_zone": "Panel 4-B Longwall Center",
                "base_load": 195.0,
                "base_temp": 28.3,
                "base_methane": 220.0,
            },
            {
                "id": "S-104",
                "name": "Goaf Perimeter Node B",
                "lat": 23.7512,
                "lon": 86.4214,
                "depth_m": 185,
                "panel_zone": "Panel 4-B Goaf Margin East",
                "base_load": 165.0,
                "base_temp": 26.9,
                "base_methane": 175.0,
            },
            {
                "id": "S-105",
                "name": "Tailgate Return Airway Node",
                "lat": 23.7503,
                "lon": 86.4232,
                "depth_m": 190,
                "panel_zone": "Panel 4-B Return Airway",
                "base_load": 130.0,
                "base_temp": 29.8,
                "base_methane": 280.0,
            },
            {
                "id": "S-106",
                "name": "Surface Haul Road Pillar Node",
                "lat": 23.7546,
                "lon": 86.4188,
                "depth_m": 30,
                "panel_zone": "Haul Road Overburden",
                "base_load": 95.0,
                "base_temp": 24.2,
                "base_methane": 40.0,
            },
            {
                "id": "S-107",
                "name": "Village Barrier Sub-Surface Node",
                "lat": 23.7541,
                "lon": 86.4218,
                "depth_m": 45,
                "panel_zone": "Village Buffer Zone 1",
                "base_load": 85.0,
                "base_temp": 24.8,
                "base_methane": 35.0,
            },
            {
                "id": "S-108",
                "name": "Railway Line Settlement Node",
                "lat": 23.7529,
                "lon": 86.4248,
                "depth_m": 25,
                "panel_zone": "Coal Freight Rail Corridor",
                "base_load": 110.0,
                "base_temp": 25.1,
                "base_methane": 45.0,
            },
        ]

        self.nodes: Dict[str, SensorNode] = {}
        self._init_nodes()
        self.detector = SubsidenceAnomalyDetector()
        self._train_default_detector()

        self.step_counter = 0
        self.history_records: List[Dict] = []
        self.alert_logs: List[Dict] = []
        self.false_alarms_rejected = 0

        self.seismic_detector = get_seismic_detector()
        self.stgcn_forecaster = get_stgcn_forecaster()
        self.insar_df = load_insar_spatial_data()

    def _init_nodes(self):
        for cfg in self.initial_nodes_config:
            self.nodes[cfg["id"]] = SensorNode(
                node_id=cfg["id"],
                name=cfg["name"],
                lat=cfg["lat"],
                lon=cfg["lon"],
                depth_m=cfg["depth_m"],
                panel_zone=cfg["panel_zone"],
                base_load_kN=cfg["base_load"],
                load_kN=cfg["base_load"],
                temp_c=cfg["base_temp"],
                methane_ppm=cfg["base_methane"],
            )

    def _train_default_detector(self):
        baseline_df = self.generate_baseline_dataset(n_samples=2500)
        self.detector.fit(baseline_df)

    def generate_baseline_dataset(self, n_samples: int = 2500) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        records = []
        for _ in range(n_samples):
            pitch = rng.normal(0.12, 0.02)
            roll = rng.normal(0.08, 0.02)
            tilt_mag = math.sqrt(pitch**2 + roll**2)

            vib_rms = float(np.clip(rng.normal(0.04, 0.006), 0.015, 0.07))
            vib_peak = float(vib_rms * rng.uniform(1.8, 2.2))

            disp_mm = float(np.clip(rng.normal(0.30, 0.04), 0.08, 0.50))
            disp_rate = float(rng.normal(0.0, 0.004))

            load_delta = float(rng.normal(0.0, 1.5))
            laser_dev = float(np.clip(rng.normal(0.07, 0.018), 0.02, 0.15))
            spatial_disc = float(rng.normal(0.03, 0.01))

            records.append({
                "tilt_magnitude_deg": tilt_mag,
                "vibration_rms_g": vib_rms,
                "vibration_peak_g": vib_peak,
                "displacement_mm": disp_mm,
                "displacement_rate_mm_min": disp_rate,
                "load_delta_kN": load_delta,
                "laser_deviation_mm": laser_dev,
                "spatial_discrepancy_mm": spatial_disc,
            })
        return pd.DataFrame(records)

    def _compute_spatial_discrepancy(self, node_id: str) -> float:
        current_disp = self.nodes[node_id].displacement_mm
        other_disps = [n.displacement_mm for nid, n in self.nodes.items() if nid != node_id]
        mean_others = float(np.mean(other_disps)) if other_disps else current_disp
        return abs(current_disp - mean_others)

    def step(
        self,
        scenario: OperationalScenario = OperationalScenario.NORMAL,
        manual_disp_offset: float = 0.0,
        manual_tilt_offset: float = 0.0,
        manual_laser_offset: float = 0.0,
    ) -> Dict:
        self.step_counter += 1
        rng = np.random.default_rng()
        now_str = datetime.now().strftime("%H:%M:%S")

        laser_dx = 0.04 + rng.normal(0, 0.015) + manual_laser_offset
        laser_dy = -0.05 + rng.normal(0, 0.015)

        for nid, node in self.nodes.items():
            base_pitch = 0.12 + rng.normal(0, 0.012)
            base_roll = 0.08 + rng.normal(0, 0.012)
            base_vib_rms = float(np.clip(rng.normal(0.04, 0.005), 0.02, 0.06))
            base_vib_peak = base_vib_rms * rng.uniform(1.8, 2.2)
            base_disp = 0.30 + rng.normal(0, 0.025)

            if scenario == OperationalScenario.NORMAL:
                node.pitch_deg = base_pitch + manual_tilt_offset
                node.roll_deg = base_roll
                node.vibration_rms_g = base_vib_rms
                node.vibration_peak_g = base_vib_peak
                node.displacement_mm = max(0.05, base_disp + manual_disp_offset)
                node.displacement_rate_mm_min = round(rng.normal(0.0, 0.003), 3)
                node.load_delta_kN = round(rng.normal(0.0, 1.2), 1)
                node.load_kN = round(node.base_load_kN + node.load_delta_kN, 1)

            elif scenario == OperationalScenario.BLASTING:
                node.pitch_deg = base_pitch
                node.roll_deg = base_roll
                node.vibration_rms_g = float(rng.uniform(0.85, 1.45))
                node.vibration_peak_g = float(node.vibration_rms_g * rng.uniform(2.8, 4.0))
                node.displacement_mm = max(0.05, base_disp + rng.normal(0, 0.02))
                node.displacement_rate_mm_min = 0.002
                node.load_delta_kN = round(rng.normal(0.0, 2.0), 1)
                node.load_kN = round(node.base_load_kN + node.load_delta_kN, 1)

            elif scenario == OperationalScenario.STRATA_CREEP:
                if nid in ["S-102", "S-103", "S-104"]:
                    node.pitch_deg = 1.40 + rng.normal(0, 0.08) + manual_tilt_offset
                    node.roll_deg = 0.90 + rng.normal(0, 0.06)
                    node.vibration_rms_g = float(rng.uniform(0.12, 0.18))
                    node.vibration_peak_g = float(node.vibration_rms_g * 2.3)
                    node.displacement_mm = 2.20 + rng.normal(0, 0.12) + manual_disp_offset
                    node.displacement_rate_mm_min = 0.25
                    node.load_delta_kN = round(45.0 + rng.normal(0, 3.0), 1)
                else:
                    node.pitch_deg = base_pitch + 0.30
                    node.roll_deg = base_roll + 0.20
                    node.vibration_rms_g = base_vib_rms * 1.5
                    node.vibration_peak_g = base_vib_peak * 1.5
                    node.displacement_mm = base_disp + 0.50 + manual_disp_offset
                    node.displacement_rate_mm_min = 0.08
                    node.load_delta_kN = round(15.0 + rng.normal(0, 2.0), 1)

                node.load_kN = round(node.base_load_kN + node.load_delta_kN, 1)
                laser_dx = 1.25 + rng.normal(0, 0.05) + manual_laser_offset
                laser_dy = 0.85 + rng.normal(0, 0.05)

            elif scenario == OperationalScenario.CRITICAL_SUBSIDENCE:
                is_core = nid in ["S-102", "S-103", "S-104", "S-105"]
                if is_core:
                    node.pitch_deg = 4.10 + rng.normal(0, 0.2) + manual_tilt_offset
                    node.roll_deg = 2.60 + rng.normal(0, 0.15)
                    node.vibration_rms_g = float(rng.uniform(0.45, 0.85))
                    node.vibration_peak_g = float(node.vibration_rms_g * 3.2)
                    node.displacement_mm = 6.80 + rng.normal(0, 0.35) + manual_disp_offset
                    node.displacement_rate_mm_min = 1.55
                    node.load_delta_kN = round(120.0 + rng.normal(0, 8.0), 1)
                else:
                    node.pitch_deg = 2.20 + rng.normal(0, 0.15) + manual_tilt_offset
                    node.roll_deg = 1.30 + rng.normal(0, 0.10)
                    node.vibration_rms_g = float(rng.uniform(0.22, 0.38))
                    node.vibration_peak_g = float(node.vibration_rms_g * 2.5)
                    node.displacement_mm = 3.50 + rng.normal(0, 0.20) + manual_disp_offset
                    node.displacement_rate_mm_min = 0.72
                    node.load_delta_kN = round(60.0 + rng.normal(0, 5.0), 1)

                node.load_kN = round(node.base_load_kN + node.load_delta_kN, 1)
                laser_dx = 4.50 + rng.normal(0, 0.12) + manual_laser_offset
                laser_dy = 3.00 + rng.normal(0, 0.10)

            elif scenario == OperationalScenario.SENSOR_GLITCH:
                if nid == "S-103":
                    node.pitch_deg = 4.2 + manual_tilt_offset
                    node.roll_deg = 3.1
                    node.vibration_rms_g = 0.04
                    node.vibration_peak_g = 0.08
                    node.displacement_mm = 5.8 + manual_disp_offset
                    node.displacement_rate_mm_min = 0.0
                    node.load_delta_kN = 0.0
                else:
                    node.pitch_deg = base_pitch
                    node.roll_deg = base_roll
                    node.vibration_rms_g = base_vib_rms
                    node.vibration_peak_g = base_vib_peak
                    node.displacement_mm = base_disp
                    node.displacement_rate_mm_min = 0.0
                    node.load_delta_kN = 0.0

                node.load_kN = round(node.base_load_kN + node.load_delta_kN, 1)

            # ----- HARDWARE INJECTION (Wi-Fi AP or USB Serial) -----
            if nid == "S-103" and bridge.is_active and bridge.latest_data is not None:
                hw = bridge.latest_data
                
                # Math for Pitch & Roll from accelerometer (m/s2)
                ax = hw.get("accelX", 0.0) / 9.81
                ay = hw.get("accelY", 0.0) / 9.81
                az = hw.get("accelZ", 9.81) / 9.81
                
                try:
                    p = math.degrees(math.atan2(ay, math.sqrt(ax**2 + az**2)))
                    r = math.degrees(math.atan2(-ax, az))
                except Exception:
                    p, r = 0, 0
                
                # Override Node S-103
                node.pitch_deg = p
                node.roll_deg = r
                
                # Rough vibration estimate from gyro
                gx = hw.get("gyroX", 0.0)
                gy = hw.get("gyroY", 0.0)
                gz = hw.get("gyroZ", 0.0)
                vib = (abs(gx) + abs(gy) + abs(gz)) * 0.5
                node.vibration_rms_g = float(np.clip(vib, 0.0, 2.0))
                node.vibration_peak_g = node.vibration_rms_g * 1.5
                
                # Temperature from DHT22 or MPU
                if hw.get("dhtTemp") is not None:
                    node.temp_c = float(hw["dhtTemp"])
                elif "tempC" in hw:
                    node.temp_c = float(hw["tempC"])
                
                # Humidity from DHT22
                if hw.get("humidity") is not None:
                    node.humidity_pct = float(hw["humidity"])

                # MQ-2 Methane / Combustible Gas
                if hw.get("mq2Raw") is not None:
                    # Scale 0-4095 ADC to PPM range (0-5000 ppm)
                    node.methane_ppm = float(hw["mq2Raw"]) * (5000.0 / 4095.0)

                # Use ToF distance directly for displacement (scaled nicely)
                if hw.get("distanceMM", -1) > 0:
                    node.displacement_mm = float(hw["distanceMM"]) / 10.0
                
                # Load Cell (g to kN approximation for mining prop baseline)
                if "loadWeight" in hw and hw["loadWeight"] is not None:
                    node.load_kN = round(node.base_load_kN + (float(hw["loadWeight"]) / 1000.0 * 9.81), 1)

                node.rssi_dbm = hw.get("rssi", -65)
            # -------------------------------------------------------

            node.tilt_magnitude_deg = round(math.sqrt(node.pitch_deg**2 + node.roll_deg**2), 3)
            node.pitch_deg = round(node.pitch_deg, 3)
            node.roll_deg = round(node.roll_deg, 3)
            node.vibration_rms_g = round(node.vibration_rms_g, 3)
            node.vibration_peak_g = round(node.vibration_peak_g, 3)
            node.displacement_mm = round(max(0.01, node.displacement_mm), 3)
            node.last_updated = now_str

        self.laser_system.update_deviation(laser_dx, laser_dy)

        spatial_discrepancies = {
            nid: self._compute_spatial_discrepancy(nid) for nid in self.nodes
        }

        raw_anomaly_scores = {}
        for nid, node in self.nodes.items():
            feat = self.detector.extract_feature_vector(
                node,
                laser_dev_mm=self.laser_system.total_deviation_mm,
                spatial_discrepancy=spatial_discrepancies[nid],
            )
            score = self.detector.compute_anomaly_score(feat)
            raw_anomaly_scores[nid] = score

        filtered_scores, threat_level, rejection_event = self._apply_correlation_rules(
            raw_anomaly_scores, scenario
        )

        for nid, node in self.nodes.items():
            node.anomaly_score = filtered_scores[nid]
            if node.anomaly_score >= 0.75:
                node.status = "CRITICAL"
            elif node.anomaly_score >= 0.50:
                node.status = "WARNING"
            elif node.anomaly_score >= 0.20:
                node.status = "WATCH"
            else:
                node.status = "SAFE"

        if rejection_event:
            self.false_alarms_rejected += 1
            self.alert_logs.insert(0, {
                "time": now_str,
                "type": "FILTERED_ALARM",
                "badge": "warning",
                "message": rejection_event,
            })
        elif threat_level == ThreatLevel.CRITICAL:
            self.alert_logs.insert(0, {
                "time": now_str,
                "type": "SUBSIDENCE_ALERT",
                "badge": "danger",
                "message": f"CRITICAL SUBSIDENCE: Coordinated multi-node deformation ({max(n.displacement_mm for n in self.nodes.values()):.1f}mm) validated by Laser Ref ({self.laser_system.total_deviation_mm:.2f}mm). Initiate evacuation protocol!",
            })
        elif threat_level == ThreatLevel.WARNING:
            self.alert_logs.insert(0, {
                "time": now_str,
                "type": "STRATA_CREEP",
                "badge": "warning",
                "message": f"ELEVATED RISK: Active strata creep detected around Goaf Margins (Avg Displacement {np.mean([n.displacement_mm for n in self.nodes.values()]):.2f}mm). Precautionary inspection of Panel 4-B advised.",
            })

        self.alert_logs = self.alert_logs[:20]

        history_entry = {
            "step": self.step_counter,
            "timestamp": now_str,
            "threat_level": threat_level.value,
            "peak_anomaly_score": round(max(n.anomaly_score for n in self.nodes.values()), 3),
            "mean_anomaly_score": round(float(np.mean([n.anomaly_score for n in self.nodes.values()])), 3),
            "max_displacement_mm": round(max(n.displacement_mm for n in self.nodes.values()), 3),
            "laser_deviation_mm": self.laser_system.total_deviation_mm,
            "max_tilt_deg": round(max(n.tilt_magnitude_deg for n in self.nodes.values()), 3),
            "mean_load_kN": round(float(np.mean([n.load_kN for n in self.nodes.values()])), 1),
            "scenario": scenario.value,
        }
        self.history_records.append(history_entry)
        if len(self.history_records) > 60:
            self.history_records.pop(0)

        # Layer 1: UCI Seismic-Bumps Real Model Prediction
        seismic_features = []
        for n in self.nodes.values():
            ge = int(abs(n.vibration_rms_g) * 140000 + abs(n.load_delta_kN) * 900)
            gp = int(n.vibration_peak_g * 1500)
            me = int(max(0, n.vibration_peak_g - 0.15) * 65000)
            seismic_features.append({
                "genergy": ge, "gpuls": gp, "gdenergy": int(n.load_delta_kN),
                "gdpuls": int(n.vibration_rms_g * 100),
                "nbumps": int(me > 1000 and me < 10000),
                "nbumps2": int(me >= 10000 and me < 50000),
                "nbumps3": int(me >= 50000),
                "nbumps4": 0, "nbumps5": 0,
                "energy": me, "maxenergy": me
            })
        df_seis = pd.DataFrame(seismic_features)
        seis_scores = self.seismic_detector.predict_anomaly_scores(df_seis)

        # Layer 2: STGCN-LSTM InSAR Satellite Subsidence Forecast
        forecast_12h = self.stgcn_forecaster.predict_forecast_12h()
        peak_12h_risk = forecast_12h.max(axis=1)
        highest_risk_idx = int(np.argmax(peak_12h_risk))

        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "laser_system": asdict(self.laser_system),
            "threat_level": threat_level.value,
            "peak_anomaly_score": history_entry["peak_anomaly_score"],
            "mean_anomaly_score": history_entry["mean_anomaly_score"],
            "false_alarms_rejected": self.false_alarms_rejected,
            "rejection_event": rejection_event,
            "history": self.history_records,
            "logs": self.alert_logs,
            "uci_seismic": {
                "scores": {nid: float(s) for nid, s in zip(self.nodes.keys(), seis_scores)},
                "features": seismic_features,
            },
            "insar_forecast": {
                "nodes": self.insar_df.to_dict(orient="records"),
                "forecast_12h": forecast_12h.tolist(),
                "peak_12h_risk": peak_12h_risk.tolist(),
                "highest_risk_idx": highest_risk_idx,
            },
        }

    def _apply_correlation_rules(
        self, raw_scores: Dict[str, float], scenario: OperationalScenario
    ) -> Tuple[Dict[str, float], ThreatLevel, Optional[str]]:
        filtered = dict(raw_scores)
        rejection_event = None

        max_vibration = max(n.vibration_rms_g for n in self.nodes.values())
        max_displacement = max(n.displacement_mm for n in self.nodes.values())
        laser_dev = self.laser_system.total_deviation_mm

        # Rule 1: Blasting Transient Rejection
        if max_vibration > 0.6 and max_displacement < 1.0 and laser_dev < 0.5:
            rejection_event = (
                f"Multi-Node False Alarm Suppressed: Blasting shockwave (RMS {max_vibration:.2f}g) "
                f"rejected. Zero permanent displacement ({max_displacement:.2f}mm) & stable laser reference ({laser_dev:.2f}mm)."
            )
            for nid in filtered:
                filtered[nid] = round(min(0.05, filtered[nid] * 0.10), 3)
            return filtered, ThreatLevel.SAFE, rejection_event

        # Rule 2: Single Node Glitch Rejection
        elevated_nodes = [nid for nid, s in raw_scores.items() if s > 0.35]
        if len(elevated_nodes) == 1:
            glitch_node = elevated_nodes[0]
            if laser_dev < 0.5:
                rejection_event = (
                    f"Sensor Glitch Suppressed: Node {glitch_node} reported isolated anomaly score {raw_scores[glitch_node]:.2f}, "
                    f"but 0 neighboring nodes and laser reference ({laser_dev:.2f}mm) confirmed movement. Suppressed from mine alarm."
                )
                filtered[glitch_node] = 0.15
                return filtered, ThreatLevel.SAFE, rejection_event

        peak_score = max(filtered.values())
        if peak_score >= 0.70 and len(elevated_nodes) >= 3 and laser_dev > 2.2:
            threat = ThreatLevel.CRITICAL
        elif peak_score >= 0.40 and (len(elevated_nodes) >= 2 or laser_dev > 0.8):
            threat = ThreatLevel.WARNING
        elif peak_score >= 0.20:
            threat = ThreatLevel.WATCH
        else:
            threat = ThreatLevel.SAFE

        return filtered, threat, None
