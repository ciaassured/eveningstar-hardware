# EveningStar Hardware

<p align="center">
  <img src="https://github.com/ciaassured/eveningstar-hardware/releases/latest/download/EveningStar-turntable.webp" alt="Rotating 3D render of the EveningStar PCB" width="320">
</p>

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
