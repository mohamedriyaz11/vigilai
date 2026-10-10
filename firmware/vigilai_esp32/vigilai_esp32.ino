/*
  VigilAI ESP32 Actuator Firmware
  Vishwakarma Awards 2026-27 | Application ID: VK26-AU-HCI-0036
  Theme 9: HCI 2.0 (Agentic Hardware & Embodied Intelligent Systems)

  Hardware:
  - Microcontroller: ESP32-WROOM-32
  - Micro Servo PWM: GPIO18 (LEDC Channel 0, 50Hz, 16-bit resolution)
  - Status Indicator LED: GPIO4 (Active HIGH)
  - Hardware Mute Switch: GPIO15 (Active LOW with internal INPUT_PULLUP)
  - UART Serial: 115200 baud, Binary CRC-8 Protocol (0xAA header)
*/

#include <Arduino.h>

// Pin Configurations
#define PIN_SERVO        18
#define PIN_STATUS_LED    4
#define PIN_MUTE_SWITCH  15

// LEDC PWM Parameters for MG90S Servo (50Hz = 20ms period)
#define LEDC_CHANNEL_SERVO 0
#define LEDC_FREQ_HZ       50
#define LEDC_RESOLUTION    16 // 16-bit: 0 to 65535
#define SERVO_MIN_US       500  // 0 deg
#define SERVO_MAX_US       2500 // 180 deg

// Soft Limits and Safety Constraints
#define SERVO_MIN_DEG      10.0f
#define SERVO_MAX_DEG     170.0f
#define SERVO_PARK_DEG     90.0f
#define SLEW_RATE_DPS     120.0f // Maximum 120 degrees per second
#define WATCHDOG_TIMEOUT_MS 500  // Failsafe triggers if no heartbeat within 500ms
#define REACH_TIMEOUT_MS   2000  // Detach if target not reached within 2 seconds

// Protocol Definitions
#define PROTOCOL_SOF       0xAA
#define PROTOCOL_POLY      0x07

#define CMD_POINT          0x01
#define CMD_PARK           0x02
#define CMD_DETACH         0x03
#define CMD_HEARTBEAT      0x04
#define CMD_STATUS_REQUEST 0x05
#define CMD_STATUS_REPLY   0x81

// System States
enum SystemState {
  STATE_IDLE       = 0,
  STATE_PARKED     = 1,
  STATE_ACTIVE     = 2,
  STATE_WATCHDOG   = 3,
  STATE_MUTED      = 4
};

// Global Runtime State
float currentAngle = SERVO_PARK_DEG;
float targetAngle  = SERVO_PARK_DEG;
bool  isAttached   = false;
bool  isMuted      = false;
SystemState systemState = STATE_PARKED;

unsigned long lastHeartbeatTime = 0;
unsigned long lastSlewUpdateTime = 0;
unsigned long targetSetTime = 0;
unsigned long lastBlinkTime = 0;
bool ledBlinkState = false;

// Serial Protocol Parser State Machine
enum RxState {
  RX_WAIT_SOF,
  RX_READ_LEN,
  RX_READ_CMD,
  RX_READ_PAYLOAD,
  RX_READ_CRC
};

RxState rxState = RX_WAIT_SOF;
uint8_t rxLen = 0;
uint8_t rxCmd = 0;
uint8_t rxPayload[32];
uint8_t rxPayloadIdx = 0;

// CRC-8 Calculation (Polynomial 0x07)
uint8_t calculateCRC8(const uint8_t *data, size_t length) {
  uint8_t crc = 0x00;
  for (size_t i = 0; i < length; i++) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; bit++) {
      if (crc & 0x80) {
        crc = ((crc << 1) ^ PROTOCOL_POLY) & 0xFF;
      } else {
        crc = (crc << 1) & 0xFF;
      }
    }
  }
  return crc;
}

// Convert angle (0-180) to 16-bit LEDC duty cycle
uint32_t angleToDuty(float angle) {
  float clamped = constrain(angle, 0.0f, 180.0f);
  float pulseUs = SERVO_MIN_US + (clamped / 180.0f) * (SERVO_MAX_US - SERVO_MIN_US);
  // Period = 20,000 us (50Hz); duty = (pulseUs / 20000.0) * 65535
  return (uint32_t)((pulseUs / 20000.0f) * 65535.0f);
}

void attachServo() {
  if (!isAttached && !isMuted) {
    ledcAttachPin(PIN_SERVO, LEDC_CHANNEL_SERVO);
    isAttached = true;
  }
}

void detachServo() {
  if (isAttached) {
    ledcDetachPin(PIN_SERVO);
    digitalWrite(PIN_SERVO, LOW);
    isAttached = false;
  }
}

void sendStatusReply() {
  uint8_t payload[3];
  payload[0] = (uint8_t)round(currentAngle);
  payload[1] = isMuted ? 1 : 0;
  payload[2] = (uint8_t)systemState;

  uint8_t header[2] = {3, CMD_STATUS_REPLY};
  uint8_t crcBuf[5];
  crcBuf[0] = 3;
  crcBuf[1] = CMD_STATUS_REPLY;
  crcBuf[2] = payload[0];
  crcBuf[3] = payload[1];
  crcBuf[4] = payload[2];

  uint8_t crc = calculateCRC8(crcBuf, 5);

  Serial.write(PROTOCOL_SOF);
  Serial.write(3);
  Serial.write(CMD_STATUS_REPLY);
  Serial.write(payload, 3);
  Serial.write(crc);
}

void processCommand(uint8_t cmd, const uint8_t *payload, uint8_t len) {
  lastHeartbeatTime = millis();

  switch (cmd) {
    case CMD_POINT:
      if (!isMuted && len >= 1) {
        float angle = constrain((float)payload[0], SERVO_MIN_DEG, SERVO_MAX_DEG);
        targetAngle = angle;
        targetSetTime = millis();
        systemState = STATE_ACTIVE;
        attachServo();
      }
      break;

    case CMD_PARK:
      targetAngle = SERVO_PARK_DEG;
      targetSetTime = millis();
      systemState = STATE_PARKED;
      attachServo();
      break;

    case CMD_DETACH:
      detachServo();
      systemState = STATE_IDLE;
      break;

    case CMD_HEARTBEAT:
      // Heartbeat keepalive acknowledged
      if (systemState == STATE_WATCHDOG) {
        systemState = STATE_PARKED;
      }
      break;

    case CMD_STATUS_REQUEST:
      sendStatusReply();
      break;

    default:
      break;
  }
}

void updateRxParser() {
  while (Serial.available()) {
    uint8_t b = Serial.read();

    switch (rxState) {
      case RX_WAIT_SOF:
        if (b == PROTOCOL_SOF) {
          rxState = RX_READ_LEN;
        }
        break;

      case RX_READ_LEN:
        rxLen = b;
        if (rxLen > 32) {
          rxState = RX_WAIT_SOF; // Invalid length
        } else {
          rxState = RX_READ_CMD;
        }
        break;

      case RX_READ_CMD:
        rxCmd = b;
        rxPayloadIdx = 0;
        if (rxLen == 0) {
          rxState = RX_READ_CRC;
        } else {
          rxState = RX_READ_PAYLOAD;
        }
        break;

      case RX_READ_PAYLOAD:
        rxPayload[rxPayloadIdx++] = b;
        if (rxPayloadIdx >= rxLen) {
          rxState = RX_READ_CRC;
        }
        break;

      case RX_READ_CRC: {
        uint8_t checkBuf[34];
        checkBuf[0] = rxLen;
        checkBuf[1] = rxCmd;
        for (uint8_t i = 0; i < rxLen; i++) {
          checkBuf[2 + i] = rxPayload[i];
        }
        uint8_t computedCRC = calculateCRC8(checkBuf, 2 + rxLen);
        if (computedCRC == b) {
          processCommand(rxCmd, rxPayload, rxLen);
        }
        rxState = RX_WAIT_SOF;
        break;
      }
    }
  }
}

void updateSlewRate() {
  unsigned long now = millis();
  float dt = (now - lastSlewUpdateTime) / 1000.0f;
  lastSlewUpdateTime = now;

  if (dt <= 0.0f || dt > 0.1f) dt = 0.01f;

  if (isAttached && !isMuted) {
    float delta = targetAngle - currentAngle;
    float maxStep = SLEW_RATE_DPS * dt;

    if (abs(delta) <= maxStep) {
      currentAngle = targetAngle;
    } else {
      currentAngle += (delta > 0.0f ? maxStep : -maxStep);
    }

    ledcWrite(LEDC_CHANNEL_SERVO, angleToDuty(currentAngle));

    // If target not reached within 2 seconds, safety detach
    if (abs(currentAngle - targetAngle) > 1.0f && (now - targetSetTime > REACH_TIMEOUT_MS)) {
      detachServo();
      systemState = STATE_IDLE;
    }
  }
}

void updateWatchdogAndLeds() {
  unsigned long now = millis();

  // Read hardware mute switch (Active LOW with pullup)
  bool mutePressed = (digitalRead(PIN_MUTE_SWITCH) == LOW);
  if (mutePressed != isMuted) {
    isMuted = mutePressed;
    if (isMuted) {
      detachServo();
      systemState = STATE_MUTED;
      digitalWrite(PIN_STATUS_LED, LOW);
    } else {
      systemState = STATE_PARKED;
    }
  }

  if (isMuted) {
    digitalWrite(PIN_STATUS_LED, LOW);
    return;
  }

  // Check 500ms Watchdog Timer
  if (now - lastHeartbeatTime > WATCHDOG_TIMEOUT_MS) {
    systemState = STATE_WATCHDOG;
    targetAngle = SERVO_PARK_DEG;
    detachServo();

    // Fast blink indicator for watchdog failsafe (10Hz)
    if (now - lastBlinkTime > 100) {
      lastBlinkTime = now;
      ledBlinkState = !ledBlinkState;
      digitalWrite(PIN_STATUS_LED, ledBlinkState ? HIGH : LOW);
    }
  } else {
    // Normal active or parked operation: solid green LED
    digitalWrite(PIN_STATUS_LED, HIGH);
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_MUTE_SWITCH, INPUT_PULLUP);

  // Initialize LEDC PWM timer
  ledcSetup(LEDC_CHANNEL_SERVO, LEDC_FREQ_HZ, LEDC_RESOLUTION);
  attachServo();
  ledcWrite(LEDC_CHANNEL_SERVO, angleToDuty(SERVO_PARK_DEG));

  lastHeartbeatTime = millis();
  lastSlewUpdateTime = millis();
  targetSetTime = millis();
}

void loop() {
  updateRxParser();
  updateSlewRate();
  updateWatchdogAndLeds();
  delay(2); // Non-blocking loop cycle
}
