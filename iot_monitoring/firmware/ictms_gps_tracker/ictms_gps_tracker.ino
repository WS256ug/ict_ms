#include <SoftwareSerial.h>
#include <TinyGPS++.h>

SoftwareSerial gpsSerial(4, 3);   // GPS TX -> Arduino pin 4
SoftwareSerial gsmSerial(7, 8);   // SIM900A TX -> Arduino pin 7, SIM900A RX -> Arduino pin 8

TinyGPSPlus gps;

const char DEVICE_ID[] = "IUIU-PR-001";
const char API_KEY[] = "nUZJHHHE6WAm6_H5OxogCwVPIBn_ZA3LPzxoYka4Bcc";
const char APN[] = "internet";

// SIM900A uses HTTP, not HTTPS
const char SERVER_URL[] = "http://ict-ms.vercel.app/iot/gps/ingest/";

const unsigned long SEND_INTERVAL_MS = 20000;
const unsigned long MAX_FIX_AGE_MS = 10000;

unsigned long lastSendAt = 0;

void clearGsm() {
  while (gsmSerial.available()) {
    gsmSerial.read();
  }
}

bool waitForResponse(const char *expected, unsigned long timeoutMs) {
  String response = "";
  unsigned long startTime = millis();

  while (millis() - startTime < timeoutMs) {
    while (gsmSerial.available()) {
      char c = gsmSerial.read();
      Serial.write(c);
      response += c;

      if (response.indexOf(expected) != -1) {
        return true;
      }

      if (response.indexOf("ERROR") != -1) {
        return false;
      }
    }
  }

  return false;
}

bool sendAT(String command, const char *expected, unsigned long timeoutMs) {
  gsmSerial.listen();
  clearGsm();

  Serial.print(">> ");
  Serial.println(command);

  gsmSerial.println(command);
  return waitForResponse(expected, timeoutMs);
}

bool initGPRS() {
  Serial.println("Initializing SIM900A GPRS...");

  if (!sendAT("AT", "OK", 3000)) {
    Serial.println("SIM900A not responding.");
    return false;
  }

  sendAT("ATE0", "OK", 3000);
  sendAT("AT+CSQ", "OK", 3000);
  sendAT("AT+CREG?", "OK", 3000);

  if (!sendAT("AT+CGATT=1", "OK", 10000)) {
    Serial.println("GPRS attach failed.");
    return false;
  }

  sendAT("AT+SAPBR=0,1", "OK", 5000);

  if (!sendAT("AT+SAPBR=3,1,\"CONTYPE\",\"GPRS\"", "OK", 5000)) {
    Serial.println("CONTYPE failed.");
    return false;
  }

  if (!sendAT(String("AT+SAPBR=3,1,\"APN\",\"") + APN + "\"", "OK", 5000)) {
    Serial.println("APN failed.");
    return false;
  }

  if (!sendAT("AT+SAPBR=1,1", "OK", 25000)) {
    Serial.println("Bearer open failed.");
    return false;
  }

  if (!sendAT("AT+SAPBR=2,1", "+SAPBR:", 10000)) {
    Serial.println("Bearer check failed.");
    return false;
  }

  Serial.println("GPRS connected.");
  gpsSerial.listen();
  return true;
}

bool sendLocation(double lat, double lon) {
  String url = String(SERVER_URL) +
               "?id=" + DEVICE_ID +
               "&key=" + API_KEY +
               "&lat=" + String(lat, 6) +
               "&lon=" + String(lon, 6);

  Serial.println("Sending location to ICT-MS...");

  sendAT("AT+HTTPTERM", "OK", 3000);

  if (!sendAT("AT+HTTPINIT", "OK", 5000)) {
    Serial.println("HTTPINIT failed.");
    return false;
  }

  if (!sendAT("AT+HTTPPARA=\"CID\",1", "OK", 5000)) {
    Serial.println("CID failed.");
    sendAT("AT+HTTPTERM", "OK", 3000);
    return false;
  }

  if (!sendAT(String("AT+HTTPPARA=\"URL\",\"") + url + "\"", "OK", 10000)) {
    Serial.println("URL failed.");
    sendAT("AT+HTTPTERM", "OK", 3000);
    return false;
  }

  if (!sendAT("AT+HTTPACTION=0", "+HTTPACTION:", 40000)) {
    Serial.println("HTTP GET failed.");
    sendAT("AT+HTTPTERM", "OK", 3000);
    return false;
  }

  sendAT("AT+HTTPREAD", "OK", 10000);
  sendAT("AT+HTTPTERM", "OK", 3000);

  Serial.println("Location sent.");
  gpsSerial.listen();
  return true;
}

void setup() {
  Serial.begin(9600);
  gpsSerial.begin(9600);
  gsmSerial.begin(9600);

  delay(5000);

  Serial.println("GPS + SIM900A tracker starting...");

  if (!initGPRS()) {
    Serial.println("GPRS failed. Will retry.");
  }

  gpsSerial.listen();
}

void loop() {
  gpsSerial.listen();

  while (gpsSerial.available()) {
    gps.encode(gpsSerial.read());
  }

  if (millis() - lastSendAt < SEND_INTERVAL_MS) {
    return;
  }

  lastSendAt = millis();

  if (!gps.location.isValid() || gps.location.age() > MAX_FIX_AGE_MS) {
    Serial.println("Waiting for fresh GPS fix...");
    return;
  }

  double lat = gps.location.lat();
  double lon = gps.location.lng();

  Serial.print("LAT: ");
  Serial.println(lat, 6);

  Serial.print("LON: ");
  Serial.println(lon, 6);

  if (!sendLocation(lat, lon)) {
    Serial.println("Location send failed.");
    initGPRS();
  }
}