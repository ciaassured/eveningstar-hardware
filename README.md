# EveningStar Hardware

The hardware design for an isolated ESP32-based interface that communicates with Morningstar solar charge controllers over the Morningstar MeterBus RJ11 interface.

This project implements a protected half-duplex physical layer for interfacing an ESP32 UART with the Morningstar MeterBus used by devices such as the ProStar MPPT series.

## Features

- Full galvanic isolation between ESP32 and MeterBus
- Half-duplex open-drain bus interface
- Designed for noisy and long cable environments
- TVS and PTC protected bus input
- Schmitt-trigger conditioned receive path
- ESP32 compatible UART interface
- Debug LEDs for TX/RX activity and power
- KiCad project files included

## Bus Overview

Morningstar MeterBus is a single-wire open-collector style serial bus exposed on an RJ11 connector.

Observed characteristics:

- Idle high
- Active low
- Half duplex
- 9600 baud
- Bus-powered accessory interface
- Separate power and data pins

This project is intended for use with Morningstar controllers such as:

- ProStar MPPT
- TriStar MPPT
- Other Morningstar controllers exposing MeterBus

## Debug LEDs

The debug LEDs on the MeterBus side of the circuit may help you debug communication issues.

The a lit green LED indicates power is being supplied from the Morningstar controller, and a blinking green light indicates that data is being sent from the Morningstar controller to the ESP32 (RX).

A blinking red LED indicates data is being sent from the ESP32 to the Morningstar controller (TX).

## Hardware Observations

This section contains measurements and observations of the Morningstar charge controller and MeterBus interface at various voltages applied to the controller's battery terminals.

### General Observations

- The MPPT charge controller supports both **12VDC** and **24VDC** battery systems.
- The controller appears to shut down at approximately **4.5VDC** battery voltage.
- The controller boots again at approximately **5.6VDC** battery voltage.
- Current sourcing capability of the MeterBus `POWER` pins is currently unknown.
- The MeterBus `POWER` pins appear to be internally regulated to approximately **12VDC** during normal operation.
- The document [`Meterbus Adapter Instructions`](./docs/operation-manual-pc-meterbus-adapter-en.pdf) specifies a valid MeterBus power range of **8VDC – 15.5VDC**.
- All `GND` pins appear to be internally bridged together.
- All `POWER` pins appear to be internally bridged together.
- All measurements are relative to MeterBus `GND`.

### MeterBus Measurements

| Battery Voltage | MeterBus POWER | MeterBus TX/RX Idle |
|---|---:|---:|
| 24VDC | 11.9VDC | 7.5VDC |
| 13.9VDC | 11.9VDC | - |
| 12VDC | 11.0VDC | 7.5VDC |
| 8VDC | 7.0VDC | 6.5VDC |
| 7VDC | 6.0VDC | 5.6VDC |

Resistance measurements taken while the unit was powered off

- 330 uA shorting TX/RX to GND
- 35 KOhm between TX/RX and GND
- 20 KOhm between TX/RX and POWER

### Preliminary Conclusions

- The MeterBus `POWER` pins appear to provide a maximum voltage output of around **11.9VDC** which roughly follows the battery voltage.
- The TX/RX line appears to idle below the MeterBus `POWER` voltage.
- The TX/RX idle voltage remains relatively stable across both 12V and 24V systems, but drops as the battery voltage goes below **12VDC**.

## Disclaimer

This project is experimental and not affiliated with or endorsed by Morningstar Corporation.

Use at your own risk when interfacing with battery and solar equipment.

### AI Assistance

Portions of this project have been created or modified with AI-assisted tools.
AI-generated suggestions can be incomplete or incorrect and must not be treated
as engineering certification. Independently review the schematics, PCB layout,
component ratings, isolation boundaries, and fabrication outputs, and perform
appropriate electrical, thermal, safety, and regulatory validation before
manufacturing or using the hardware.
