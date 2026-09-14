/*
  ============================================================
                 PROJECT SOOCHAK
       ESP32 SENSOR NODE - Wi-Fi AP MODE
  ============================================================

  ESP32 creates its own Wi-Fi network.

  Wi-Fi:
    SSID     : SOOCHAK_NODE
    Password : soochak123

  ESP32 IP:
    192.168.4.1

  Laptop connects to SOOCHAK_NODE.
  ESP32 sends HTTP POST requests to the laptop.

  EDIT THESE FOR YOUR WEBSITE:
    SERVER_IP
    SERVER_PORT
    SERVER_PATH

  Sensors:
    MPU6050 (I2C: SDA=21, SCL=22)
    VL53L0X ToF (I2C: SDA=21, SCL=22)
    HX711 + Load Cell (DOUT=32, SCK=33)
    DHT22 (DATA=25)
    MQ-2 Gas (AO=34)
    Buzzer (PIN=27)

  LoRa is NOT required.
  ============================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>

#include "Adafruit_VL53L0X.h"
#include "HX711.h"
#include "DHT.h"


// ============================================================
// WIFI ACCESS POINT
// ============================================================

#define WIFI_SSID       "SOOCHAK_NODE"
#define WIFI_PASSWORD   "soochak123"

IPAddress apIP(192, 168, 4, 1);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);


// ============================================================
// YOUR LAPTOP SERVER
// ============================================================
//
// Your laptop will normally receive:
// 192.168.4.2
//
// CHANGE THESE TO MATCH YOUR WEBSITE.
//

#define SERVER_IP       "192.168.4.2"
#define SERVER_PORT     3000
#define SERVER_PATH     "/api/sensors"


// ============================================================
// I2C
// ============================================================

#define PIN_I2C_SDA 21
#define PIN_I2C_SCL 22


// ============================================================
// MPU6050
// ============================================================

#define MPU_ADDR 0x68

int16_t rawAccelX;
int16_t rawAccelY;
int16_t rawAccelZ;

int16_t rawGyroX;
int16_t rawGyroY;
int16_t rawGyroZ;

int16_t rawTemp;

bool mpuOk = false;


// ============================================================
// VL53L0X
// ============================================================

Adafruit_VL53L0X tof = Adafruit_VL53L0X();

bool tofOk = false;


// ============================================================
// HX711 + LOAD CELL
// ============================================================

#define PIN_HX711_DOUT 32
#define PIN_HX711_SCK  33

HX711 scale;

bool hx711Ok = false;

// Your current calibration factor
float calibrationFactor = 14550.0;


// ============================================================
// DHT22
// ============================================================

#define PIN_DHT22 25
#define DHT_TYPE DHT22

DHT dht(PIN_DHT22, DHT_TYPE);

bool dhtOk = false;


// ============================================================
// MQ-2
// ============================================================

#define PIN_MQ2_AO 34

/*
  IMPORTANT:

  MQ-2 AO
       |
      10k
       |
       +------ GPIO 34
       |
      20k
       |
      GND
*/

#define MQ2_ALARM_THRESHOLD 2500

int mq2Raw = 0;
bool mq2Alarm = false;


// ============================================================
// BUZZER
// ============================================================

#define PIN_BUZZER 27

bool buzzerState = false;


// ============================================================
// TIMING
// ============================================================

unsigned long lastCycle = 0;

const unsigned long SENSOR_INTERVAL = 3000;

uint32_t packetCount = 0;


// ============================================================
// MPU6050 INITIALIZATION
// ============================================================

bool initMPU() {

  // Wake MPU6050
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0x00);

  if (Wire.endTransmission() != 0) {
    return false;
  }


  // Accelerometer ±4G
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x1C);
  Wire.write(0x08);

  if (Wire.endTransmission() != 0) {
    return false;
  }


  // Gyroscope ±500 deg/s
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x1B);
  Wire.write(0x08);

  if (Wire.endTransmission() != 0) {
    return false;
  }


  return true;
}


// ============================================================
// READ MPU6050
// ============================================================

void readMPUData() {

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);

  Wire.requestFrom(
    (uint8_t)MPU_ADDR,
    (size_t)14
  );


  if (Wire.available() == 14) {

    rawAccelX = (Wire.read() << 8) | Wire.read();
    rawAccelY = (Wire.read() << 8) | Wire.read();
    rawAccelZ = (Wire.read() << 8) | Wire.read();

    rawTemp = (Wire.read() << 8) | Wire.read();

    rawGyroX = (Wire.read() << 8) | Wire.read();
    rawGyroY = (Wire.read() << 8) | Wire.read();
    rawGyroZ = (Wire.read() << 8) | Wire.read();
  }
}


// ============================================================
// SEND DATA TO LAPTOP
// ============================================================

void sendToServer(
  float accelX,
  float accelY,
  float accelZ,

  float gyroX,
  float gyroY,
  float gyroZ,

  float mpuTempC,

  int distanceMM,

  float loadWeight,

  float dhtTemperature,
  float dhtHumidity,

  int mq2Raw,
  bool mq2Alarm
) {

  HTTPClient http;


  // Build URL
  String url =
    "http://" +
    String(SERVER_IP) +
    ":" +
    String(SERVER_PORT) +
    String(SERVER_PATH);


  Serial.println();
  Serial.println(F("[HTTP] Sending telemetry..."));
  Serial.print(F("[HTTP] URL: "));
  Serial.println(url);


  http.begin(url);

  http.addHeader(
    "Content-Type",
    "application/json"
  );


  // ==========================================================
  // JSON
  // ==========================================================

  String json = "{";

  json += "\"packet\":";
  json += String(packetCount);

  json += ",\"accel_x\":";
  json += String(accelX, 3);

  json += ",\"accel_y\":";
  json += String(accelY, 3);

  json += ",\"accel_z\":";
  json += String(accelZ, 3);


  json += ",\"gyro_x\":";
  json += String(gyroX, 3);

  json += ",\"gyro_y\":";
  json += String(gyroY, 3);

  json += ",\"gyro_z\":";
  json += String(gyroZ, 3);


  json += ",\"mpu_temp\":";
  json += String(mpuTempC, 2);


  json += ",\"distance_mm\":";
  json += String(distanceMM);


  json += ",\"load_g\":";
  json += String(loadWeight, 2);


  json += ",\"dht_temp\":";

  if (isnan(dhtTemperature)) {
    json += "null";
  } else {
    json += String(dhtTemperature, 2);
  }


  json += ",\"humidity\":";

  if (isnan(dhtHumidity)) {
    json += "null";
  } else {
    json += String(dhtHumidity, 2);
  }


  json += ",\"mq2_raw\":";
  json += String(mq2Raw);


  json += ",\"gas_alarm\":";

  if (mq2Alarm) {
    json += "true";
  } else {
    json += "false";
  }


  json += "}";


  Serial.print(F("[HTTP] JSON: "));
  Serial.println(json);


  // ==========================================================
  // POST
  // ==========================================================

  int httpCode = http.POST(json);


  if (httpCode > 0) {

    Serial.print(F("[HTTP] Response code: "));
    Serial.println(httpCode);


    String response = http.getString();

    Serial.print(F("[HTTP] Response: "));
    Serial.println(response);

  } else {

    Serial.print(F("[HTTP] POST failed: "));
    Serial.println(http.errorToString(httpCode));
  }


  http.end();
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  delay(1000);


  Serial.println();
  Serial.println(F("================================================"));
  Serial.println(F("          PROJECT SOOCHAK"));
  Serial.println(F("       WI-FI SENSOR NODE"));
  Serial.println(F("================================================"));


  // ==========================================================
  // I2C
  // ==========================================================

  Serial.println();
  Serial.println(F("[INIT] Starting I2C..."));

  Wire.begin(
    PIN_I2C_SDA,
    PIN_I2C_SCL
  );


  // ==========================================================
  // MPU6050
  // ==========================================================

  Serial.print(F("[INIT] MPU6050 ............... "));

  mpuOk = initMPU();

  if (mpuOk) {
    Serial.println(F("SUCCESS"));
  } else {
    Serial.println(F("FAILED"));
  }


  // ==========================================================
  // VL53L0X
  // ==========================================================

  Serial.print(F("[INIT] VL53L0X ............... "));

  tofOk = tof.begin();

  if (tofOk) {
    Serial.println(F("SUCCESS"));
  } else {
    Serial.println(F("FAILED"));
  }


  // ==========================================================
  // HX711
  // ==========================================================

  Serial.print(F("[INIT] HX711 ................ "));

  scale.begin(
    PIN_HX711_DOUT,
    PIN_HX711_SCK
  );


  if (scale.is_ready()) {

    hx711Ok = true;

    scale.set_scale(
      calibrationFactor
    );

    /*
      IMPORTANT:
      Start ESP32 with NO weight on the
      load cell when using tare().
    */

    Serial.println(F("SUCCESS"));

    Serial.println(
      F("[HX711] Removing any load...")
    );

    delay(2000);

    scale.tare(20);

    Serial.println(
      F("[HX711] Tare complete")
    );

  } else {

    hx711Ok = false;

    Serial.println(F("FAILED"));
  }


  // ==========================================================
  // DHT22
  // ==========================================================

  Serial.print(F("[INIT] DHT22 ................. "));

  dht.begin();

  delay(1500);


  float testHumidity =
    dht.readHumidity();

  float testTemperature =
    dht.readTemperature();


  if (
    !isnan(testHumidity) &&
    !isnan(testTemperature)
  ) {

    dhtOk = true;

    Serial.println(F("SUCCESS"));

  } else {

    dhtOk = false;

    Serial.println(F("FAILED"));
  }


  // ==========================================================
  // MQ-2
  // ==========================================================

  Serial.print(F("[INIT] MQ-2 .................. "));

  pinMode(
    PIN_MQ2_AO,
    INPUT
  );


  analogReadResolution(12);

  analogSetPinAttenuation(
    PIN_MQ2_AO,
    ADC_11db
  );


  mq2Raw =
    analogRead(PIN_MQ2_AO);


  Serial.println(F("SUCCESS"));

  Serial.println(
    F("[MQ-2] Sensor requires warm-up")
  );


  // ==========================================================
  // BUZZER
  // ==========================================================

  Serial.print(F("[INIT] Buzzer ................. "));

  pinMode(
    PIN_BUZZER,
    OUTPUT
  );

  digitalWrite(
    PIN_BUZZER,
    LOW
  );

  Serial.println(F("SUCCESS"));


  // ==========================================================
  // WI-FI ACCESS POINT
  // ==========================================================

  Serial.println();
  Serial.println(F("[WIFI] Starting Access Point..."));


  WiFi.mode(WIFI_AP);


  WiFi.softAPConfig(
    apIP,
    gateway,
    subnet
  );


  bool apStarted =
    WiFi.softAP(
      WIFI_SSID,
      WIFI_PASSWORD
    );


  if (apStarted) {

    Serial.println(
      F("[WIFI] Access Point started")
    );

    Serial.print(
      F("[WIFI] SSID: ")
    );

    Serial.println(
      WIFI_SSID
    );

    Serial.print(
      F("[WIFI] Password: ")
    );

    Serial.println(
      WIFI_PASSWORD
    );

    Serial.print(
      F("[WIFI] ESP32 IP: ")
    );

    Serial.println(
      WiFi.softAPIP()
    );

  } else {

    Serial.println(
      F("[WIFI] FAILED TO START AP")
    );
  }


  // ==========================================================
  // COMPLETE
  // ==========================================================

  Serial.println();
  Serial.println(F("================================================"));
  Serial.println(F("             SOOCHAK READY"));
  Serial.println(F("================================================"));

  Serial.println();
  Serial.println(
    F("1. Connect laptop to SOOCHAK_NODE")
  );

  Serial.println(
    F("2. Laptop should receive IP 192.168.4.x")
  );

  Serial.println(
    F("3. Run your local website/backend")
  );

  Serial.println(
    F("4. ESP32 will POST sensor data")
  );

  Serial.println();
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  // ==========================================================
  // TELEMETRY INTERVAL
  // ==========================================================

  if (
    millis() - lastCycle <
    SENSOR_INTERVAL
  ) {

    delay(20);

    return;
  }


  lastCycle =
    millis();


  packetCount++;


  // ==========================================================
  // VARIABLES
  // ==========================================================

  float accelX = 0;
  float accelY = 0;
  float accelZ = 0;

  float gyroX = 0;
  float gyroY = 0;
  float gyroZ = 0;

  float mpuTempC = 0;

  int distanceMM = -1;

  float loadWeight = 0;

  float dhtTemperature = NAN;
  float dhtHumidity = NAN;


  // ==========================================================
  // MPU6050
  // ==========================================================

  if (mpuOk) {

    readMPUData();


    // ±4G = 8192 LSB/G

    accelX =
      (float)rawAccelX /
      8192.0 *
      9.81;

    accelY =
      (float)rawAccelY /
      8192.0 *
      9.81;

    accelZ =
      (float)rawAccelZ /
      8192.0 *
      9.81;


    // ±500 deg/s
    // Convert deg/s -> rad/s

    gyroX =
      (float)rawGyroX /
      65.5 *
      (3.14159 / 180.0);

    gyroY =
      (float)rawGyroY /
      65.5 *
      (3.14159 / 180.0);

    gyroZ =
      (float)rawGyroZ /
      65.5 *
      (3.14159 / 180.0);


    /*
      MPU6050 temperature correction
      from your current Soochak setup.
    */

    mpuTempC =
      ((float)rawTemp / 340.0)
      + 36.53
      - 15.0;
  }


  // ==========================================================
  // VL53L0X
  // ==========================================================

  if (tofOk) {

    VL53L0X_RangingMeasurementData_t measure;


    tof.rangingTest(
      &measure,
      false
    );


    if (
      measure.RangeStatus != 4
    ) {

      distanceMM =
        measure.RangeMilliMeter;
    }
  }


  // ==========================================================
  // HX711
  // ==========================================================

  if (
    hx711Ok &&
    scale.is_ready()
  ) {

    loadWeight =
      scale.get_units(5);


    /*
      Ignore tiny fluctuations around zero.
    */

    if (
      loadWeight > -2.0 &&
      loadWeight < 2.0
    ) {

      loadWeight = 0;
    }
  }


  // ==========================================================
  // DHT22
  // ==========================================================

  if (dhtOk) {

    dhtHumidity =
      dht.readHumidity();

    dhtTemperature =
      dht.readTemperature();


    if (
      isnan(dhtHumidity) ||
      isnan(dhtTemperature)
    ) {

      Serial.println(
        F("[WARNING] DHT22 read failed")
      );
    }
  }


  // ==========================================================
  // MQ-2
  // ==========================================================

  mq2Raw =
    analogRead(PIN_MQ2_AO);


  if (
    mq2Raw >=
    MQ2_ALARM_THRESHOLD
  ) {

    mq2Alarm = true;

  } else {

    mq2Alarm = false;
  }


  // ==========================================================
  // BUZZER
  // ==========================================================

  if (mq2Alarm) {

    digitalWrite(
      PIN_BUZZER,
      HIGH
    );

    buzzerState = true;

  } else {

    digitalWrite(
      PIN_BUZZER,
      LOW
    );

    buzzerState = false;
  }


  // ==========================================================
  // SERIAL OUTPUT
  // ==========================================================

  Serial.println();
  Serial.println(
    F("---------------- TELEMETRY ----------------")
  );


  Serial.print(
    F("Packet       : ")
  );

  Serial.println(
    packetCount
  );


  Serial.print(
    F("Accel        : ")
  );

  Serial.print(accelX, 2);
  Serial.print(F(", "));
  Serial.print(accelY, 2);
  Serial.print(F(", "));
  Serial.println(accelZ, 2);


  Serial.print(
    F("Gyro         : ")
  );

  Serial.print(gyroX, 2);
  Serial.print(F(", "));
  Serial.print(gyroY, 2);
  Serial.print(F(", "));
  Serial.println(gyroZ, 2);


  Serial.print(
    F("MPU Temp     : ")
  );

  Serial.print(
    mpuTempC,
    1
  );

  Serial.println(F(" C"));


  Serial.print(
    F("Distance     : ")
  );

  Serial.print(
    distanceMM
  );

  Serial.println(F(" mm"));


  Serial.print(
    F("Load         : ")
  );

  Serial.print(
    loadWeight,
    1
  );

  Serial.println(F(" g"));


  Serial.print(
    F("DHT Temp     : ")
  );

  if (isnan(dhtTemperature)) {
    Serial.println(F("N/A"));
  } else {
    Serial.print(
      dhtTemperature,
      1
    );

    Serial.println(F(" C"));
  }


  Serial.print(
    F("Humidity     : ")
  );

  if (isnan(dhtHumidity)) {
    Serial.println(F("N/A"));
  } else {
    Serial.print(
      dhtHumidity,
      1
    );

    Serial.println(F(" %"));
  }


  Serial.print(
    F("MQ-2 Raw     : ")
  );

  Serial.println(
    mq2Raw
  );


  Serial.print(
    F("Gas Alarm    : ")
  );

  Serial.println(
    mq2Alarm ?
    F("ALARM") :
    F("NORMAL")
  );


  Serial.print(
    F("Buzzer       : ")
  );

  Serial.println(
    buzzerState ?
    F("ON") :
    F("OFF")
  );


  // ==========================================================
  // SEND TO LAPTOP
  // ==========================================================

  sendToServer(

    accelX,
    accelY,
    accelZ,

    gyroX,
    gyroY,
    gyroZ,

    mpuTempC,

    distanceMM,

    loadWeight,

    dhtTemperature,
    dhtHumidity,

    mq2Raw,
    mq2Alarm
  );


  Serial.println(
    F("-------------------------------------------")
  );
}
