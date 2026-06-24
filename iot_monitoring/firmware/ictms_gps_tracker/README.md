# ICT-MS GPS/GSM tracker

This Arduino sketch sends a fresh GPS position every 20 seconds to:

`https://ict-ms.vercel.app/iot/gps/ingest/`

## Libraries

- `TinyGPSPlus`
- Arduino's built-in `SoftwareSerial`

## Wiring used by the sketch

| Module | Module pin | Arduino pin |
|---|---|---|
| GPS | TX | 4 (RX) |
| GPS | RX | 3 (TX, normally unused) |
| GSM | TX | 7 (RX) |
| GSM | RX | 8 (TX) |

Use a common ground. A SIM800-class modem needs a stable high-current power
supply and must not be powered from the Arduino's 5V pin. Protect a 2.8V GSM
RX input from a 5V Arduino TX signal with a suitable divider or level shifter.

## Configuration

Edit these values near the top of the sketch:

- `DEVICE_ID`: must match an active `TrackerDevice.device_id`
- `API_KEY`: must match that tracker's API key
- `APN`: must match the SIM card provider
- `SERVER_URL`: keep HTTPS because the production host redirects HTTP traffic

In Django admin, create or update the tracker under **IoT Monitoring > Tracker
devices**, link it to the correct asset, and mark it active.

The sketch uses an HTTPS form POST. The server returns plain text `OK` with HTTP
status 200 after a reading is saved.

## Troubleshooting

- `Waiting for a fresh GPS fix`: move the GPS antenna outdoors with a clear sky.
- `GPRS initialization failed`: verify SIM registration, airtime/data, APN, and
  modem power.
- `HTTPACTION` is not 200: inspect the serial monitor for the returned status.
- `AT+HTTPSSL=1` fails: the modem firmware does not support the server's TLS;
  use a newer modem such as SIM7600 rather than putting the API key on an
  unencrypted public HTTP connection.
