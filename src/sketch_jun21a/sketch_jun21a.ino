#include <Arduino.h>
#include <ETH.h>
#include <Network.h>
#include <SPI.h>
#include <Wire.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "soc/soc_caps.h"

#if SOC_USB_SERIAL_JTAG_SUPPORTED
#include "HWCDC.h"
#endif

#define MCU_LED 0
#define METERBUS_READ 14
#define METERBUS_WRITE 15
#define ETH_MOSI 18
#define ETH_SCK 19
#define ETH_MISO 20
#define ETH_CS 21
#define ETH_INT 22
#define ETH_RST 23
#define AHT20_SDA 2
#define AHT20_SCL 3

constexpr uint32_t USB_BAUD = 9600;
constexpr uint32_t METERBUS_BAUD = 9600;
constexpr uint32_t AHT20_I2C_HZ = 100000;
constexpr size_t SERIAL_BUFFER_SIZE = 64;
constexpr bool ENABLE_METERBUS_BRIDGE = false;
constexpr bool ENABLE_MODBUS_READER = true;
constexpr bool ENABLE_AHT20_READER = true;
constexpr bool ENABLE_W5500_SPI_TEST = true;
constexpr bool ENABLE_ETHERNET_NETWORK = true;
constexpr bool ENABLE_ETHERNET_LED_ACTIVITY_PULSE = true;
constexpr bool ENABLE_REQUEST_SERIAL_LOGS = false;
constexpr bool USE_STATIC_IP = true;
constexpr uint32_t W5500_SPI_HZ = 1000000;
constexpr uint8_t W5500_ETH_SPI_MHZ = 20;
constexpr int32_t W5500_PHY_ADDR = 1;
constexpr uint32_t ETHERNET_LINK_POLL_MS = 1000;
constexpr uint32_t ETHERNET_LED_PULSE_INTERVAL_MS = 1000;
constexpr uint16_t ETHERNET_LED_PULSE_LOCAL_PORT = 49152;
constexpr uint16_t ETHERNET_LED_PULSE_REMOTE_PORT = 9;
constexpr uint8_t MODBUS_UNIT_ID = 1;
constexpr uint8_t MODBUS_FUNCTION_READ_INPUT_REGISTERS = 0x04;
constexpr uint16_t MODBUS_BATTERY_VOLTAGE_REGISTER = 0x0023;
constexpr uint16_t MODBUS_REGISTER_COUNT = 1;
constexpr uint32_t MODBUS_RESPONSE_TIMEOUT_MS = 1200;
constexpr size_t MODBUS_MAX_FRAME_SIZE = 32;
constexpr uint8_t AHT20_ADDRESS = 0x38;
constexpr uint32_t AHT20_MEASUREMENT_TIMEOUT_MS = 200;
constexpr uint32_t HTTP_REQUEST_TIMEOUT_MS = 250;
constexpr uint32_t HTTP_CLIENT_TIMEOUT_MS = 500;
constexpr uint8_t HTTP_CLIENTS_PER_LOOP = 4;
constexpr size_t HTTP_RESPONSE_BODY_BUFFER_SIZE = 8192;

constexpr uint16_t W5500_REG_MR = 0x0000;
constexpr uint16_t W5500_REG_IR = 0x0015;
constexpr uint16_t W5500_REG_PHYCFGR = 0x002E;
constexpr uint16_t W5500_REG_VERSIONR = 0x0039;
constexpr uint8_t W5500_COMMON_READ = 0x00;
constexpr uint8_t W5500_COMMON_WRITE = 0x04;
constexpr uint8_t W5500_EXPECTED_VERSION = 0x04;

HardwareSerial meterbus(1);
SPISettings w5500SpiSettings(W5500_SPI_HZ, MSBFIRST, SPI_MODE0);
NetworkServer statusServer(80, 8);
NetworkUDP ledPulseUdp;

IPAddress staticIp(192, 168, 7, 2);
IPAddress staticDns(192, 168, 7, 1);
IPAddress staticGateway(192, 168, 7, 1);
IPAddress staticSubnet(255, 255, 255, 0);

enum class NetworkState : uint8_t {
  WaitingForLink,
  WaitingForIp,
  Ready,
  Failed,
};

NetworkState networkState = NetworkState::WaitingForLink;
uint32_t lastEthernetPollMs = 0;
uint32_t lastLedPulseMs = 0;
uint32_t ledPulseCounter = 0;
bool lastLinkUp = false;
bool ethDriverStarted = false;
bool statusServerStarted = false;
uint8_t w5500VersionRegister = 0;
float batteryVoltageVolts = NAN;
uint16_t batteryVoltageRaw = 0;
uint32_t modbusLastReadMs = 0;
uint32_t modbusSuccessCount = 0;
uint32_t modbusErrorCount = 0;
bool modbusLastReadOk = false;
char modbusLastError[80] = "not read yet";
float aht20TemperatureCelsius = NAN;
float aht20HumidityPercent = NAN;
uint32_t aht20LastReadMs = 0;
uint32_t aht20SuccessCount = 0;
uint32_t aht20ErrorCount = 0;
bool aht20LastReadOk = false;
char aht20LastError[80] = "not read yet";
uint32_t httpAcceptedCount = 0;
uint32_t httpCompletedCount = 0;
uint32_t httpReadErrorCount = 0;
uint32_t httpWriteErrorCount = 0;
uint32_t httpNotFoundCount = 0;
uint32_t httpLastRequestDurationMs = 0;
uint32_t httpLastResponseBytes = 0;
uint8_t httpActiveRequests = 0;
bool httpLastWriteOk = false;
bool httpLastResponseTruncated = false;
char httpResponseBody[HTTP_RESPONSE_BODY_BUFFER_SIZE];

#if SOC_USB_SERIAL_JTAG_SUPPORTED && !(ARDUINO_USB_MODE && ARDUINO_USB_CDC_ON_BOOT)
HWCDC usbSerialJtag;
#define USB_SERIAL usbSerialJtag
#else
#define USB_SERIAL Serial
#endif

static void bridgeSerial(Stream &from, Stream &to) {
  uint8_t buffer[SERIAL_BUFFER_SIZE];
  size_t length = 0;

  while (from.available() > 0 && length < sizeof(buffer)) {
    buffer[length++] = static_cast<uint8_t>(from.read());
  }

  if (length > 0) {
    to.write(buffer, length);
  }
}

static void setModbusError(const char *message) {
  strncpy(modbusLastError, message, sizeof(modbusLastError) - 1);
  modbusLastError[sizeof(modbusLastError) - 1] = '\0';
}

static uint16_t crc16Modbus(const uint8_t *data, size_t length) {
  uint16_t crc = 0xFFFF;

  for (size_t index = 0; index < length; index++) {
    crc ^= data[index];

    for (uint8_t bit = 0; bit < 8; bit++) {
      if ((crc & 0x0001) != 0) {
        crc = static_cast<uint16_t>((crc >> 1) ^ 0xA001);
      } else {
        crc >>= 1;
      }
    }
  }

  return crc;
}

static size_t buildReadInputRegisterRequest(uint8_t *request, uint8_t unitId, uint16_t address, uint16_t count) {
  request[0] = unitId;
  request[1] = MODBUS_FUNCTION_READ_INPUT_REGISTERS;
  request[2] = static_cast<uint8_t>(address >> 8);
  request[3] = static_cast<uint8_t>(address & 0xFF);
  request[4] = static_cast<uint8_t>(count >> 8);
  request[5] = static_cast<uint8_t>(count & 0xFF);

  const uint16_t crc = crc16Modbus(request, 6);
  request[6] = static_cast<uint8_t>(crc & 0xFF);
  request[7] = static_cast<uint8_t>(crc >> 8);
  return 8;
}

static size_t expectedModbusResponseLength(const uint8_t *response, size_t length) {
  if (length < 2) {
    return 0;
  }

  if ((response[1] & 0x80) != 0) {
    return 5;
  }

  if (length < 3) {
    return 0;
  }

  return static_cast<size_t>(5 + response[2]);
}

static bool readModbusResponseIgnoringEcho(
    const uint8_t *request,
    size_t requestLength,
    uint8_t *response,
    size_t responseCapacity,
    size_t *responseLength) {
  uint8_t echoCandidate[8];
  size_t echoCandidateLength = 0;
  *responseLength = 0;

  const uint32_t startMs = millis();
  while (millis() - startMs < MODBUS_RESPONSE_TIMEOUT_MS) {
    if (meterbus.available() <= 0) {
      delay(1);
      continue;
    }

    const int readValue = meterbus.read();
    if (readValue < 0) {
      continue;
    }

    const uint8_t byteValue = static_cast<uint8_t>(readValue);

    if (*responseLength == 0 && echoCandidateLength < requestLength) {
      if (byteValue == request[echoCandidateLength]) {
        echoCandidate[echoCandidateLength++] = byteValue;
        continue;
      }

      for (size_t index = 0; index < echoCandidateLength; index++) {
        if (*responseLength >= responseCapacity) {
          setModbusError("modbus response buffer overflow");
          return false;
        }
        response[(*responseLength)++] = echoCandidate[index];
      }
      echoCandidateLength = 0;
    }

    if (*responseLength >= responseCapacity) {
      setModbusError("modbus response buffer overflow");
      return false;
    }
    response[(*responseLength)++] = byteValue;

    const size_t expectedLength = expectedModbusResponseLength(response, *responseLength);
    if (expectedLength > 0 && *responseLength >= expectedLength) {
      return true;
    }
  }

  setModbusError("modbus response timeout");
  return false;
}

static bool validateModbusResponse(
    const uint8_t *response,
    size_t responseLength,
    uint8_t unitId,
    uint8_t functionCode,
    uint16_t expectedRegisterCount) {
  if (responseLength < 5) {
    setModbusError("modbus response too short");
    return false;
  }

  const uint16_t actualCrc = static_cast<uint16_t>(response[responseLength - 2] | (response[responseLength - 1] << 8));
  const uint16_t expectedCrc = crc16Modbus(response, responseLength - 2);
  if (actualCrc != expectedCrc) {
    setModbusError("modbus response crc mismatch");
    return false;
  }

  if (response[0] != unitId) {
    setModbusError("modbus response unit mismatch");
    return false;
  }

  if ((response[1] & 0x80) != 0) {
    snprintf(modbusLastError, sizeof(modbusLastError), "modbus exception %u", response[2]);
    return false;
  }

  if (response[1] != functionCode) {
    setModbusError("modbus response function mismatch");
    return false;
  }

  if (response[2] != expectedRegisterCount * 2) {
    setModbusError("modbus response byte count mismatch");
    return false;
  }

  return true;
}

static float decodeFloat16(uint16_t raw) {
  const int sign = (raw & 0x8000) ? -1 : 1;
  const uint16_t exponent = static_cast<uint16_t>((raw >> 10) & 0x1F);
  const uint16_t fraction = static_cast<uint16_t>(raw & 0x03FF);

  if (exponent == 0) {
    if (fraction == 0) {
      return sign < 0 ? -0.0f : 0.0f;
    }
    return sign * ldexpf(static_cast<float>(fraction), -24);
  }

  if (exponent == 0x1F) {
    if (fraction == 0) {
      return sign < 0 ? -INFINITY : INFINITY;
    }
    return NAN;
  }

  return sign * ldexpf(1.0f + (static_cast<float>(fraction) / 1024.0f), static_cast<int>(exponent) - 15);
}

static bool readBatteryVoltageRegister() {
  uint8_t request[8];
  uint8_t response[MODBUS_MAX_FRAME_SIZE];
  size_t responseLength = 0;

  const size_t requestLength = buildReadInputRegisterRequest(
      request,
      MODBUS_UNIT_ID,
      MODBUS_BATTERY_VOLTAGE_REGISTER,
      MODBUS_REGISTER_COUNT);

  while (meterbus.available() > 0) {
    meterbus.read();
  }

  meterbus.write(request, requestLength);
  meterbus.flush();

  if (!readModbusResponseIgnoringEcho(request, requestLength, response, sizeof(response), &responseLength)) {
    return false;
  }

  if (!validateModbusResponse(
          response,
          responseLength,
          MODBUS_UNIT_ID,
          MODBUS_FUNCTION_READ_INPUT_REGISTERS,
          MODBUS_REGISTER_COUNT)) {
    return false;
  }

  batteryVoltageRaw = static_cast<uint16_t>((response[3] << 8) | response[4]);
  batteryVoltageVolts = decodeFloat16(batteryVoltageRaw);
  setModbusError("");
  return true;
}

static void pollModbusReader() {
  if (!ENABLE_MODBUS_READER || ENABLE_METERBUS_BRIDGE) {
    return;
  }

  modbusLastReadMs = millis();
  modbusLastReadOk = readBatteryVoltageRegister();

  if (modbusLastReadOk) {
    modbusSuccessCount++;
    if (ENABLE_REQUEST_SERIAL_LOGS) {
      USB_SERIAL.print("Battery voltage: ");
      USB_SERIAL.print(batteryVoltageVolts, 3);
      USB_SERIAL.print(" V raw=0x");
      printHexByte(static_cast<uint8_t>(batteryVoltageRaw >> 8));
      printHexByte(static_cast<uint8_t>(batteryVoltageRaw & 0xFF));
      USB_SERIAL.println();
    }
  } else {
    modbusErrorCount++;
    if (ENABLE_REQUEST_SERIAL_LOGS) {
      USB_SERIAL.print("Battery voltage read failed: ");
      USB_SERIAL.println(modbusLastError);
    }
  }
}

static void setAht20Error(const char *message) {
  strncpy(aht20LastError, message, sizeof(aht20LastError) - 1);
  aht20LastError[sizeof(aht20LastError) - 1] = '\0';
}

static uint8_t crc8Aht20(const uint8_t *data, size_t length) {
  uint8_t crc = 0xFF;

  for (size_t index = 0; index < length; index++) {
    crc ^= data[index];
    for (uint8_t bit = 0; bit < 8; bit++) {
      if ((crc & 0x80) != 0) {
        crc = static_cast<uint8_t>((crc << 1) ^ 0x31);
      } else {
        crc <<= 1;
      }
    }
  }

  return crc;
}

static bool aht20WriteCommand(uint8_t command, uint8_t arg0 = 0, uint8_t arg1 = 0, bool includeArgs = true) {
  Wire.beginTransmission(AHT20_ADDRESS);
  Wire.write(command);
  if (includeArgs) {
    Wire.write(arg0);
    Wire.write(arg1);
  }

  if (Wire.endTransmission() != 0) {
    setAht20Error("aht20 i2c write failed");
    return false;
  }

  return true;
}

static bool aht20ReadStatus(uint8_t *status) {
  if (Wire.requestFrom(AHT20_ADDRESS, static_cast<uint8_t>(1)) != 1) {
    setAht20Error("aht20 status read failed");
    return false;
  }

  *status = Wire.read();
  return true;
}

static bool setupAht20() {
  if (!ENABLE_AHT20_READER) {
    return true;
  }

  Wire.begin(AHT20_SDA, AHT20_SCL);
  Wire.setClock(AHT20_I2C_HZ);
  delay(40);

  uint8_t status = 0;
  if (!aht20ReadStatus(&status)) {
    USB_SERIAL.print("AHT20 init failed: ");
    USB_SERIAL.println(aht20LastError);
    return false;
  }

  if ((status & 0x08) == 0) {
    if (!aht20WriteCommand(0xBE, 0x08, 0x00)) {
      USB_SERIAL.print("AHT20 init failed: ");
      USB_SERIAL.println(aht20LastError);
      return false;
    }
    delay(10);
  }

  USB_SERIAL.print("AHT20 I2C started at address 0x");
  printHexByte(AHT20_ADDRESS);
  USB_SERIAL.print(" SDA=");
  USB_SERIAL.print(AHT20_SDA);
  USB_SERIAL.print(" SCL=");
  USB_SERIAL.println(AHT20_SCL);
  setAht20Error("");
  return true;
}

static bool readAht20() {
  if (!aht20WriteCommand(0xAC, 0x33, 0x00)) {
    return false;
  }

  const uint32_t startMs = millis();
  uint8_t data[7] = {0};

  while (millis() - startMs < AHT20_MEASUREMENT_TIMEOUT_MS) {
    delay(80);

    if (Wire.requestFrom(AHT20_ADDRESS, static_cast<uint8_t>(7)) != 7) {
      setAht20Error("aht20 measurement read failed");
      return false;
    }

    for (size_t index = 0; index < sizeof(data); index++) {
      data[index] = Wire.read();
    }

    if ((data[0] & 0x80) == 0) {
      if (crc8Aht20(data, 6) != data[6]) {
        setAht20Error("aht20 crc mismatch");
        return false;
      }

      const uint32_t rawHumidity =
          (static_cast<uint32_t>(data[1]) << 12) |
          (static_cast<uint32_t>(data[2]) << 4) |
          (static_cast<uint32_t>(data[3]) >> 4);
      const uint32_t rawTemperature =
          ((static_cast<uint32_t>(data[3]) & 0x0F) << 16) |
          (static_cast<uint32_t>(data[4]) << 8) |
          static_cast<uint32_t>(data[5]);

      aht20HumidityPercent = (static_cast<float>(rawHumidity) * 100.0f) / 1048576.0f;
      aht20TemperatureCelsius = ((static_cast<float>(rawTemperature) * 200.0f) / 1048576.0f) - 50.0f;
      setAht20Error("");
      return true;
    }
  }

  setAht20Error("aht20 measurement timeout");
  return false;
}

static void pollAht20Reader() {
  if (!ENABLE_AHT20_READER) {
    return;
  }

  aht20LastReadMs = millis();
  aht20LastReadOk = readAht20();

  if (aht20LastReadOk) {
    aht20SuccessCount++;
    if (ENABLE_REQUEST_SERIAL_LOGS) {
      USB_SERIAL.print("AHT20 temperature: ");
      USB_SERIAL.print(aht20TemperatureCelsius, 2);
      USB_SERIAL.print(" C humidity: ");
      USB_SERIAL.print(aht20HumidityPercent, 2);
      USB_SERIAL.println(" %");
    }
  } else {
    aht20ErrorCount++;
    if (ENABLE_REQUEST_SERIAL_LOGS) {
      USB_SERIAL.print("AHT20 read failed: ");
      USB_SERIAL.println(aht20LastError);
    }
  }
}

static void waitForUsbSerial(uint32_t timeoutMs) {
  const uint32_t startMs = millis();

  while (!USB_SERIAL && millis() - startMs < timeoutMs) {
    delay(10);
  }
}

static void printHexByte(uint8_t value) {
  if (value < 0x10) {
    USB_SERIAL.print('0');
  }
  USB_SERIAL.print(value, HEX);
}

static void printIpAddress(IPAddress address) {
  for (uint8_t index = 0; index < 4; index++) {
    if (index > 0) {
      USB_SERIAL.print('.');
    }
    USB_SERIAL.print(address[index]);
  }
}

static IPAddress localBroadcastAddress() {
  const IPAddress localIp = ETH.localIP();
  const IPAddress subnet = ETH.subnetMask();

  return IPAddress(
      localIp[0] | static_cast<uint8_t>(~subnet[0]),
      localIp[1] | static_cast<uint8_t>(~subnet[1]),
      localIp[2] | static_cast<uint8_t>(~subnet[2]),
      localIp[3] | static_cast<uint8_t>(~subnet[3]));
}

static uint8_t w5500ReadRegister(uint16_t address) {
  SPI.beginTransaction(w5500SpiSettings);
  digitalWrite(ETH_CS, LOW);
  SPI.transfer(static_cast<uint8_t>(address >> 8));
  SPI.transfer(static_cast<uint8_t>(address & 0xFF));
  SPI.transfer(W5500_COMMON_READ);
  const uint8_t value = SPI.transfer(0x00);
  digitalWrite(ETH_CS, HIGH);
  SPI.endTransaction();

  return value;
}

static bool w5500LinkIsUp() {
  return (w5500ReadRegister(W5500_REG_PHYCFGR) & 0x01) != 0;
}

static void w5500WriteRegister(uint16_t address, uint8_t value) {
  SPI.beginTransaction(w5500SpiSettings);
  digitalWrite(ETH_CS, LOW);
  SPI.transfer(static_cast<uint8_t>(address >> 8));
  SPI.transfer(static_cast<uint8_t>(address & 0xFF));
  SPI.transfer(W5500_COMMON_WRITE);
  SPI.transfer(value);
  digitalWrite(ETH_CS, HIGH);
  SPI.endTransaction();
}

static void w5500HardwareReset() {
  digitalWrite(ETH_CS, HIGH);
  digitalWrite(ETH_RST, LOW);
  delay(10);
  digitalWrite(ETH_RST, HIGH);
  delay(250);
}

static void printW5500Register(const char *name, uint16_t address) {
  USB_SERIAL.print(name);
  USB_SERIAL.print(" = 0x");
  printHexByte(w5500ReadRegister(address));
  USB_SERIAL.println();
}

static void printW5500PhyStatus() {
  const uint8_t phycfgr = w5500ReadRegister(W5500_REG_PHYCFGR);

  USB_SERIAL.print("PHYCFGR = 0x");
  printHexByte(phycfgr);
  USB_SERIAL.print("  link=");
  USB_SERIAL.print((phycfgr & 0x01) ? "up" : "down");
  USB_SERIAL.print("  speed=");
  USB_SERIAL.print((phycfgr & 0x02) ? "100M" : "10M");
  USB_SERIAL.print("  duplex=");
  USB_SERIAL.println((phycfgr & 0x04) ? "full" : "half");
}

static bool w5500SpiProbe() {
  USB_SERIAL.println();
  USB_SERIAL.println("W5500 SPI probe");
  USB_SERIAL.print("SPI pins: SCK=");
  USB_SERIAL.print(ETH_SCK);
  USB_SERIAL.print(" MISO=");
  USB_SERIAL.print(ETH_MISO);
  USB_SERIAL.print(" MOSI=");
  USB_SERIAL.print(ETH_MOSI);
  USB_SERIAL.print(" CS=");
  USB_SERIAL.print(ETH_CS);
  USB_SERIAL.print(" INT=");
  USB_SERIAL.print(ETH_INT);
  USB_SERIAL.print(" RST=");
  USB_SERIAL.println(ETH_RST);
  USB_SERIAL.print("SPI clock: ");
  USB_SERIAL.print(W5500_SPI_HZ);
  USB_SERIAL.println(" Hz");

  w5500HardwareReset();

  const uint8_t version = w5500ReadRegister(W5500_REG_VERSIONR);
  w5500VersionRegister = version;
  USB_SERIAL.print("VERSIONR = 0x");
  printHexByte(version);
  USB_SERIAL.print("  expected 0x");
  printHexByte(W5500_EXPECTED_VERSION);
  USB_SERIAL.println(version == W5500_EXPECTED_VERSION ? "  OK" : "  FAIL");

  printW5500Register("MR", W5500_REG_MR);
  printW5500Register("IR", W5500_REG_IR);
  printW5500PhyStatus();

  if (version != W5500_EXPECTED_VERSION) {
    USB_SERIAL.println("SPI probe failed. Check 3V3A, CS, SCK, MOSI, MISO, reset, and common ground.");
    return false;
  }

  USB_SERIAL.println("Issuing W5500 soft reset...");
  w5500WriteRegister(W5500_REG_MR, 0x80);
  delay(10);
  printW5500Register("MR after reset", W5500_REG_MR);
  w5500VersionRegister = w5500ReadRegister(W5500_REG_VERSIONR);
  USB_SERIAL.print("VERSIONR after reset = 0x");
  printHexByte(w5500VersionRegister);
  USB_SERIAL.println();
  USB_SERIAL.println("W5500 SPI probe passed.");
  return true;
}

static void printEthernetConfig() {
  USB_SERIAL.print("MAC address: ");
  USB_SERIAL.println(ETH.macAddress());
  USB_SERIAL.print("IP address: ");
  printIpAddress(ETH.localIP());
  USB_SERIAL.println();
  USB_SERIAL.print("Subnet: ");
  printIpAddress(ETH.subnetMask());
  USB_SERIAL.println();
  USB_SERIAL.print("Gateway: ");
  printIpAddress(ETH.gatewayIP());
  USB_SERIAL.println();
  USB_SERIAL.print("DNS: ");
  printIpAddress(ETH.dnsIP());
  USB_SERIAL.println();
}

static void printEthernetDriverLinkStatus() {
  const bool linkUp = ETH.linkUp();

  USB_SERIAL.print("Ethernet driver link=");
  USB_SERIAL.print(linkUp ? "up" : "down");
  USB_SERIAL.print(" speed=");
  USB_SERIAL.print(linkUp ? ETH.linkSpeed() : 0);
  USB_SERIAL.print("M duplex=");
  USB_SERIAL.println(linkUp && ETH.fullDuplex() ? "full" : "half");
}

static void startStatusServer() {
  if (statusServerStarted) {
    return;
  }

  statusServer.begin();
  statusServer.setNoDelay(true);
  statusServer.setTimeout(1);
  statusServerStarted = true;
  USB_SERIAL.print("HTTP status server: http://");
  printIpAddress(ETH.localIP());
  USB_SERIAL.println("/");

  if (ENABLE_ETHERNET_LED_ACTIVITY_PULSE) {
    ledPulseUdp.begin(ETHERNET_LED_PULSE_LOCAL_PORT);
    lastLedPulseMs = 0;
    ledPulseCounter = 0;
    USB_SERIAL.print("Activity LED pulse: UDP broadcast every ");
    USB_SERIAL.print(ETHERNET_LED_PULSE_INTERVAL_MS);
    USB_SERIAL.println(" ms");
  }
}

static void startStaticIp() {
  if (!ETH.config(staticIp, staticGateway, staticSubnet, staticDns)) {
    USB_SERIAL.println("Static IPv4 configuration failed.");
    networkState = NetworkState::Failed;
    return;
  }

  USB_SERIAL.println("Static IPv4 configured; waiting for link/IP event.");
}

static void stopStatusServer() {
  if (!statusServerStarted) {
    return;
  }

  statusServer.stop();
  ledPulseUdp.stop();
  statusServerStarted = false;
}

static void onNetworkEvent(arduino_event_id_t event, arduino_event_info_t info) {
  (void)info;

  switch (event) {
    case ARDUINO_EVENT_ETH_START:
      USB_SERIAL.println("ETH Started");
      ETH.setHostname("eveningstar");
      break;

    case ARDUINO_EVENT_ETH_CONNECTED:
      USB_SERIAL.println("ETH Connected");
      networkState = NetworkState::WaitingForIp;
      break;

    case ARDUINO_EVENT_ETH_GOT_IP:
      USB_SERIAL.println("ETH Got IP");
      networkState = NetworkState::Ready;
      printEthernetConfig();
      startStatusServer();
      break;

    case ARDUINO_EVENT_ETH_LOST_IP:
      USB_SERIAL.println("ETH Lost IP");
      networkState = NetworkState::WaitingForIp;
      stopStatusServer();
      break;

    case ARDUINO_EVENT_ETH_DISCONNECTED:
      USB_SERIAL.println("ETH Disconnected");
      networkState = NetworkState::WaitingForLink;
      stopStatusServer();
      break;

    case ARDUINO_EVENT_ETH_STOP:
      USB_SERIAL.println("ETH Stopped");
      networkState = NetworkState::Failed;
      stopStatusServer();
      break;

    default:
      break;
  }
}

static void setupW5500() {
  pinMode(ETH_CS, OUTPUT);
  pinMode(ETH_RST, OUTPUT);
  pinMode(ETH_INT, INPUT_PULLUP);
  digitalWrite(ETH_CS, HIGH);
  digitalWrite(ETH_RST, HIGH);

  SPI.begin(ETH_SCK, ETH_MISO, ETH_MOSI, ETH_CS);
  const bool spiOk = ENABLE_W5500_SPI_TEST ? w5500SpiProbe() : true;

  if (!ENABLE_ETHERNET_NETWORK) {
    return;
  }

  if (!spiOk) {
    USB_SERIAL.println("Ethernet network setup skipped because the W5500 SPI probe failed.");
    networkState = NetworkState::Failed;
    return;
  }

  Network.onEvent(onNetworkEvent);
  USB_SERIAL.println("Starting ESP32 Ethernet driver for W5500...");
  ethDriverStarted = ETH.begin(ETH_PHY_W5500, W5500_PHY_ADDR, ETH_CS, ETH_INT, ETH_RST, SPI, W5500_ETH_SPI_MHZ);

  if (!ethDriverStarted) {
    USB_SERIAL.println("ETH.begin failed.");
    networkState = NetworkState::Failed;
    return;
  }

  if (USE_STATIC_IP) {
    startStaticIp();
  } else {
    USB_SERIAL.println("DHCP enabled; waiting for link/IP event.");
  }

  printEthernetDriverLinkStatus();

  networkState = ETH.linkUp() ? NetworkState::WaitingForIp : NetworkState::WaitingForLink;
  lastEthernetPollMs = 0;
}

static bool appendHttpBody(size_t *length, const char *format, ...) {
  if (*length >= HTTP_RESPONSE_BODY_BUFFER_SIZE) {
    return false;
  }

  va_list args;
  va_start(args, format);
  const int written = vsnprintf(
      httpResponseBody + *length,
      HTTP_RESPONSE_BODY_BUFFER_SIZE - *length,
      format,
      args);
  va_end(args);

  if (written < 0) {
    return false;
  }

  const size_t available = HTTP_RESPONSE_BODY_BUFFER_SIZE - *length;
  if (static_cast<size_t>(written) >= available) {
    *length = HTTP_RESPONSE_BODY_BUFFER_SIZE - 1;
    httpResponseBody[*length] = '\0';
    return false;
  }

  *length += static_cast<size_t>(written);
  return true;
}

static bool sendHttpTextResponse(NetworkClient &client, const char *status, const char *body, size_t bodyLength) {
  char header[192];
  const int headerLength = snprintf(
      header,
      sizeof(header),
      "HTTP/1.1 %s\r\n"
      "Content-Type: text/plain; charset=utf-8\r\n"
      "Cache-Control: no-store\r\n"
      "Connection: close\r\n"
      "Content-Length: %u\r\n"
      "\r\n",
      status,
      static_cast<unsigned int>(bodyLength));

  if (headerLength <= 0 || static_cast<size_t>(headerLength) >= sizeof(header)) {
    httpLastResponseBytes = 0;
    return false;
  }

  const size_t headerBytes = static_cast<size_t>(headerLength);
  const size_t writtenHeader = client.write(reinterpret_cast<const uint8_t *>(header), headerBytes);
  const size_t writtenBody = client.write(reinterpret_cast<const uint8_t *>(body), bodyLength);
  httpLastResponseBytes = static_cast<uint32_t>(writtenHeader + writtenBody);

  return writtenHeader == headerBytes && writtenBody == bodyLength;
}

static bool sendOpenMetricsResponse(NetworkClient &client) {
  const bool linkUp = ETH.linkUp();
  const uint16_t linkSpeed = linkUp ? ETH.linkSpeed() : 0;
  const bool fullDuplex = linkUp && ETH.fullDuplex();
  const String macAddress = ETH.macAddress();
  size_t length = 0;
  bool bodyOk = true;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_battery_voltage_volts Battery voltage read from Morningstar Modbus input register 0x0023.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_battery_voltage_volts gauge\n") && bodyOk;
  if (modbusSuccessCount > 0 && isfinite(batteryVoltageVolts)) {
    bodyOk = appendHttpBody(&length, "eveningstar_battery_voltage_volts %.4f\n", batteryVoltageVolts) && bodyOk;
  }

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_battery_voltage_raw Raw IEEE 754 binary16 value read from Morningstar Modbus input register 0x0023.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_battery_voltage_raw gauge\n") && bodyOk;
  if (modbusSuccessCount > 0) {
    bodyOk = appendHttpBody(&length, "eveningstar_battery_voltage_raw %u\n", static_cast<unsigned int>(batteryVoltageRaw)) && bodyOk;
  }

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_meterbus_modbus_last_read_success Whether the most recent Modbus read succeeded.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_meterbus_modbus_last_read_success gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_meterbus_modbus_last_read_success %u\n", static_cast<unsigned int>(modbusLastReadOk ? 1 : 0)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_meterbus_modbus_reads_total Successful Modbus read count.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_meterbus_modbus_reads_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_meterbus_modbus_reads_total %lu\n", static_cast<unsigned long>(modbusSuccessCount)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_meterbus_modbus_read_errors_total Failed Modbus read count.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_meterbus_modbus_read_errors_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_meterbus_modbus_read_errors_total %lu\n", static_cast<unsigned long>(modbusErrorCount)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_meterbus_modbus_last_read_age_seconds Seconds since the most recent Modbus read attempt.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_meterbus_modbus_last_read_age_seconds gauge\n") && bodyOk;
  if (modbusLastReadMs == 0) {
    bodyOk = appendHttpBody(&length, "eveningstar_meterbus_modbus_last_read_age_seconds NaN\n") && bodyOk;
  } else {
    bodyOk = appendHttpBody(&length, "eveningstar_meterbus_modbus_last_read_age_seconds %.3f\n", (millis() - modbusLastReadMs) / 1000.0f) && bodyOk;
  }

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_temperature_celsius Ambient temperature read from the AHT20 sensor.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_temperature_celsius gauge\n") && bodyOk;
  if (aht20SuccessCount > 0 && isfinite(aht20TemperatureCelsius)) {
    bodyOk = appendHttpBody(&length, "eveningstar_temperature_celsius %.3f\n", aht20TemperatureCelsius) && bodyOk;
  }

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_relative_humidity_percent Relative humidity read from the AHT20 sensor.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_relative_humidity_percent gauge\n") && bodyOk;
  if (aht20SuccessCount > 0 && isfinite(aht20HumidityPercent)) {
    bodyOk = appendHttpBody(&length, "eveningstar_relative_humidity_percent %.3f\n", aht20HumidityPercent) && bodyOk;
  }

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_aht20_last_read_success Whether the most recent AHT20 read succeeded.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_aht20_last_read_success gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_aht20_last_read_success %u\n", static_cast<unsigned int>(aht20LastReadOk ? 1 : 0)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_aht20_reads_total Successful AHT20 read count.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_aht20_reads_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_aht20_reads_total %lu\n", static_cast<unsigned long>(aht20SuccessCount)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_aht20_read_errors_total Failed AHT20 read count.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_aht20_read_errors_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_aht20_read_errors_total %lu\n", static_cast<unsigned long>(aht20ErrorCount)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_aht20_last_read_age_seconds Seconds since the most recent AHT20 read attempt.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_aht20_last_read_age_seconds gauge\n") && bodyOk;
  if (aht20LastReadMs == 0) {
    bodyOk = appendHttpBody(&length, "eveningstar_aht20_last_read_age_seconds NaN\n") && bodyOk;
  } else {
    bodyOk = appendHttpBody(&length, "eveningstar_aht20_last_read_age_seconds %.3f\n", (millis() - aht20LastReadMs) / 1000.0f) && bodyOk;
  }

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_w5500_link_up W5500 physical Ethernet link state.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_w5500_link_up gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_w5500_link_up %u\n", static_cast<unsigned int>(linkUp ? 1 : 0)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_w5500_speed_mbps W5500 negotiated Ethernet link speed.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_w5500_speed_mbps gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_w5500_speed_mbps %u\n", static_cast<unsigned int>(linkSpeed)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_w5500_full_duplex W5500 negotiated full duplex state.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_w5500_full_duplex gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_w5500_full_duplex %u\n", static_cast<unsigned int>(fullDuplex ? 1 : 0)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_w5500_interrupt_pin_low W5500 interrupt pin state, active low.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_w5500_interrupt_pin_low gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_w5500_interrupt_pin_low %u\n", static_cast<unsigned int>(digitalRead(ETH_INT) == LOW ? 1 : 0)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_requests_total HTTP requests accepted by the ESP32 status server.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_requests_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_requests_total %lu\n", static_cast<unsigned long>(httpAcceptedCount)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_completed_requests_total HTTP requests completed with a full response write.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_completed_requests_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_completed_requests_total %lu\n", static_cast<unsigned long>(httpCompletedCount)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_request_read_errors_total HTTP requests dropped before a valid request line was read.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_request_read_errors_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_request_read_errors_total %lu\n", static_cast<unsigned long>(httpReadErrorCount)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_response_write_errors_total HTTP responses that did not fully write to the client socket.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_response_write_errors_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_response_write_errors_total %lu\n", static_cast<unsigned long>(httpWriteErrorCount)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_not_found_requests_total HTTP requests for unsupported paths.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_not_found_requests_total counter\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_not_found_requests_total %lu\n", static_cast<unsigned long>(httpNotFoundCount)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_active_requests Currently active HTTP requests in the single loop handler.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_active_requests gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_active_requests %u\n", static_cast<unsigned int>(httpActiveRequests)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_last_request_duration_seconds Duration of the previous HTTP request handler run.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_last_request_duration_seconds gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_last_request_duration_seconds %.3f\n", httpLastRequestDurationMs / 1000.0f) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_last_response_bytes Bytes written for the previous HTTP response.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_last_response_bytes gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_last_response_bytes %lu\n", static_cast<unsigned long>(httpLastResponseBytes)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_last_write_success Whether the previous HTTP response fully wrote to the client socket.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_last_write_success gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_last_write_success %u\n", static_cast<unsigned int>(httpLastWriteOk ? 1 : 0)) && bodyOk;
  bodyOk = appendHttpBody(&length, "# HELP eveningstar_http_last_response_truncated Whether the previous generated HTTP metrics body overflowed the static buffer.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_http_last_response_truncated gauge\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "eveningstar_http_last_response_truncated %u\n", static_cast<unsigned int>(httpLastResponseTruncated ? 1 : 0)) && bodyOk;

  bodyOk = appendHttpBody(&length, "# HELP eveningstar_w5500_info Static W5500 identity and network information.\n") && bodyOk;
  bodyOk = appendHttpBody(&length, "# TYPE eveningstar_w5500_info info\n") && bodyOk;
  bodyOk = appendHttpBody(
               &length,
               "eveningstar_w5500_info{version=\"0x%02X\",ip=\"%u.%u.%u.%u\",mac=\"%s\"} 1\n",
               static_cast<unsigned int>(w5500VersionRegister),
               static_cast<unsigned int>(ETH.localIP()[0]),
               static_cast<unsigned int>(ETH.localIP()[1]),
               static_cast<unsigned int>(ETH.localIP()[2]),
               static_cast<unsigned int>(ETH.localIP()[3]),
               macAddress.c_str()) &&
           bodyOk;

  bodyOk = appendHttpBody(&length, "# EOF\n") && bodyOk;
  httpLastResponseTruncated = !bodyOk;

  return sendHttpTextResponse(client, "200 OK", httpResponseBody, length);
}

static bool sendNotFoundResponse(NetworkClient &client) {
  static const char body[] = "not found\n";
  return sendHttpTextResponse(client, "404 Not Found", body, strlen(body));
}

static bool readHttpRequestPath(NetworkClient &client, char *path, size_t pathSize) {
  char requestLine[96] = {0};
  size_t requestLineLength = 0;
  bool firstLineDone = false;
  bool currentLineBlank = true;
  const uint32_t startMs = millis();

  path[0] = '\0';

  while (client.connected() && millis() - startMs < HTTP_REQUEST_TIMEOUT_MS) {
    if (!client.available()) {
      delay(1);
      continue;
    }

    const char value = static_cast<char>(client.read());

    if (!firstLineDone && value != '\r' && value != '\n' && requestLineLength < sizeof(requestLine) - 1) {
      requestLine[requestLineLength++] = value;
      requestLine[requestLineLength] = '\0';
    }

    if (value == '\n') {
      if (!firstLineDone) {
        firstLineDone = true;
      }

      if (currentLineBlank) {
        break;
      }
      currentLineBlank = true;
    } else if (value != '\r') {
      currentLineBlank = false;
    }
  }

  if (!firstLineDone || requestLineLength == 0) {
    return false;
  }

  char method[8] = {0};
  char url[64] = {0};
  if (sscanf(requestLine, "%7s %63s", method, url) != 2) {
    return false;
  }

  if (strcmp(method, "GET") != 0 && strcmp(method, "HEAD") != 0) {
    return false;
  }

  strncpy(path, url, pathSize - 1);
  path[pathSize - 1] = '\0';

  char *query = strchr(path, '?');
  if (query != nullptr) {
    *query = '\0';
  }
  return true;
}

static void sendActivityLedPulse() {
  if (!ENABLE_ETHERNET_LED_ACTIVITY_PULSE) {
    return;
  }

  if (millis() - lastLedPulseMs < ETHERNET_LED_PULSE_INTERVAL_MS) {
    return;
  }

  lastLedPulseMs = millis();
  ledPulseCounter++;

  const IPAddress broadcastIp = localBroadcastAddress();
  char payload[48];
  snprintf(payload, sizeof(payload), "EveningStar W5500 LED pulse %lu", static_cast<unsigned long>(ledPulseCounter));

  if (ledPulseUdp.beginPacket(broadcastIp, ETHERNET_LED_PULSE_REMOTE_PORT)) {
    ledPulseUdp.write(reinterpret_cast<const uint8_t *>(payload), strlen(payload));
    ledPulseUdp.endPacket();
  }
}

static bool handleStatusServer() {
  NetworkClient client = statusServer.accept();
  if (!client) {
    return false;
  }

  const uint32_t requestStartMs = millis();
  httpAcceptedCount++;
  httpActiveRequests++;
  client.setConnectionTimeout(HTTP_CLIENT_TIMEOUT_MS);
  client.setNoDelay(true);

  char path[64] = {0};
  if (!readHttpRequestPath(client, path, sizeof(path))) {
    httpReadErrorCount++;
    httpLastRequestDurationMs = millis() - requestStartMs;
    httpLastWriteOk = false;
    httpActiveRequests--;
    client.stop();
    return true;
  }

  bool writeOk = false;
  if (strcmp(path, "/") == 0 || strcmp(path, "/metrics") == 0) {
    pollModbusReader();
    pollAht20Reader();
    writeOk = sendOpenMetricsResponse(client);
  } else {
    httpNotFoundCount++;
    writeOk = sendNotFoundResponse(client);
  }

  if (writeOk) {
    httpCompletedCount++;
  } else {
    httpWriteErrorCount++;
  }

  httpLastWriteOk = writeOk;
  httpLastRequestDurationMs = millis() - requestStartMs;
  httpActiveRequests--;
  client.stop();
  return true;
}

static void handlePendingStatusClients() {
  for (uint8_t index = 0; index < HTTP_CLIENTS_PER_LOOP; index++) {
    if (index > 0 && !statusServer.hasClient()) {
      break;
    }

    if (!handleStatusServer()) {
      break;
    }
  }
}

static void loopEthernetNetwork() {
  if (!ENABLE_ETHERNET_NETWORK || !ethDriverStarted) {
    return;
  }

  if (millis() - lastEthernetPollMs < ETHERNET_LINK_POLL_MS) {
    if (networkState == NetworkState::Ready) {
      sendActivityLedPulse();
      handlePendingStatusClients();
    }
    return;
  }

  lastEthernetPollMs = millis();

  const bool linkUp = ETH.linkUp();
  if (linkUp != lastLinkUp) {
    lastLinkUp = linkUp;
    USB_SERIAL.print("Ethernet link ");
    USB_SERIAL.println(linkUp ? "up" : "down");
    printEthernetDriverLinkStatus();
  }

  if (!linkUp) {
    networkState = NetworkState::WaitingForLink;
    USB_SERIAL.println("Waiting for Ethernet link...");
    return;
  }

  if (networkState == NetworkState::WaitingForLink) {
    networkState = NetworkState::WaitingForIp;
    USB_SERIAL.println("Waiting for IP address...");
  }

  if (ETH.hasIP() && networkState != NetworkState::Ready) {
    networkState = NetworkState::Ready;
    USB_SERIAL.println("ETH has IP");
    printEthernetConfig();
    startStatusServer();
  }

  if (networkState != NetworkState::Ready) {
    return;
  }

  sendActivityLedPulse();
  handlePendingStatusClients();
}

void setup() {
  pinMode(MCU_LED, OUTPUT);
  pinMode(METERBUS_WRITE, OUTPUT);
  pinMode(METERBUS_READ, INPUT);

  USB_SERIAL.begin(USB_BAUD);
#if SOC_USB_SERIAL_JTAG_SUPPORTED && !(ARDUINO_USB_MODE && ARDUINO_USB_CDC_ON_BOOT)
  USB_SERIAL.setTxTimeoutMs(5);
  USB_SERIAL.setTxBufferSize(2048);
#endif
  waitForUsbSerial(3000);

  if (ENABLE_METERBUS_BRIDGE || ENABLE_MODBUS_READER) {
    meterbus.begin(METERBUS_BAUD, SERIAL_8N2, METERBUS_READ, METERBUS_WRITE);
    USB_SERIAL.print("Meterbus UART started at ");
    USB_SERIAL.print(METERBUS_BAUD);
    USB_SERIAL.println(" baud 8N2");
  }

  setupAht20();

  if (ENABLE_W5500_SPI_TEST || ENABLE_ETHERNET_NETWORK) {
    setupW5500();
  }

  digitalWrite(MCU_LED, HIGH);
  delay(500);
  digitalWrite(MCU_LED, LOW);
}

void loop() {
  if (ENABLE_METERBUS_BRIDGE) {
    bridgeSerial(USB_SERIAL, meterbus);
    bridgeSerial(meterbus, USB_SERIAL);
  }

  if (ENABLE_ETHERNET_NETWORK) {
    loopEthernetNetwork();
  }
}
