# Project Soochak - ESP32 Sensor Node Firmware

This directory contains the production firmware for the **Project Soochak Physical Geotechnical Sensor Node** operating in **Wi-Fi Access Point (SoftAP) Mode**.

---

## 📡 Wi-Fi AP Mode Operation (No LoRa Required)

The ESP32 creates its own dedicated Wi-Fi network:
* **SSID**: `SOOCHAK_NODE`
* **Password**: `soochak123`
* **ESP32 Static IP**: `192.168.4.1`
* **Target Laptop Endpoint**: `http://192.168.4.2:3000/api/sensors`
* **Telemetry Cadence**: Every 3.0 seconds

When your laptop connects to `SOOCHAK_NODE`, it is automatically assigned `192.168.4.2`. The ESP32 sends HTTP POST requests containing JSON telemetry to the Project Soochak ingestion server, immediately overriding **Node S-103** with real-time physical readings.

---

## 🔌 Hardware Pinout & Wiring Table

| Sensor / Actuator | Parameter Measured | ESP32 GPIO / Bus | Wiring / Notes |
| :--- | :--- | :--- | :--- |
| **MPU6050** | 3-Axis Accel & Gyro | `SDA (GPIO 21)`, `SCL (GPIO 22)` | Standard I2C (Address `0x68`). Measures roof tilt angle and vibration RMS. |
| **VL53L0X** | Time-of-Flight Laser Distance | `SDA (GPIO 21)`, `SCL (GPIO 22)` | Shared I2C Bus. Measures extensometer crack dilation / roof sag in millimeters. |
| **HX711 + Load Cell** | Overburden Prop Load | `DOUT (GPIO 32)`, `SCK (GPIO 33)` | 24-bit ADC. Calibrated with tare at boot. Measures hydraulic prop stress (kN). |
| **DHT22** | Underground Climate | `DATA (GPIO 25)` | Requires 10k pull-up resistor. Measures ambient temperature (°C) & relative humidity (%). |
| **MQ-2** | Methane & Combustible Gas | `AO (GPIO 34)` | Analog input with 10k/20k voltage divider to protect 3.3V ADC. Alarms when raw ADC $\ge 2500$. |
| **Active Buzzer** | Audio Evacuation Siren | `PIN (GPIO 27)` | Triggered HIGH during combustible gas alarms. |

---

## 📦 Required Arduino Libraries

Install these via the Arduino Library Manager (`Ctrl+Shift+I` or `Cmd+Shift+I`):
1. **Adafruit_VL53L0X** by Adafruit
2. **HX711** by Bogdan Necula
3. **DHT sensor library** by Adafruit
4. **Adafruit Unified Sensor** by Adafruit

---

## 🚀 How to Flash & Connect

1. Open `firmware/esp32_wifi_node/esp32_wifi_node.ino` in the Arduino IDE.
2. Select Board: **ESP32 Dev Module** (or your specific ESP32 variant).
3. Upload at `115200` baud.
4. On your laptop, connect Wi-Fi to **`SOOCHAK_NODE`** (Password: **`soochak123`**).
5. Start Project Soochak (`streamlit run app.py`).
6. The dashboard will automatically latch onto the live stream on port `3000` and reflect your live hardware on Node **S-103**!
