# EveningStar Hardware

<p align="center">
  <img src="https://github.com/ciaassured/eveningstar-hardware/releases/latest/download/EveningStar-turntable.webp" alt="Rotating 3D render of the EveningStar PCB" width="320">
</p>

EveningStar is a gateway between a Morningstar MeterBus network and a standard Ethernet/IP network. It connects to the MeterBus port of a Morningstar solar charge controller or other compatible device, making the bus accessible over Ethernet for monitoring, automation, and control.

The hardware is built around an ESP32-C6 and divided into two galvanically isolated sections:

* A MeterBus interface, powered from the connected Morningstar device.
* An ESP32 and Ethernet interface, powered independently.

This isolation prevents ground loops and reduces the risk of fault currents flowing between the MeterBus network, battery system, and connected Ethernet or USB equipment.

MeterBus communication is half-duplex and open-drain. The interface includes a Schmitt-trigger receive path and transient-voltage-suppression clamps to improve reliability when cables are routed through electrically noisy environments.

The ESP32 side of the board can be powered from the battery system connected to the charge controller or from a separate external supply, even when the two systems operate at different voltages. USB-C and a dedicated debug header provide firmware flashing and console access.

Firmware is maintained separately in the [eveningstar-firmware](https://github.com/ciaassured/eveningstar-firmware) repository.

The KiCad project and its build, review, and fabrication workflow are documented in [`pcb/README.md`](pcb/README.md).

## Disclaimer

This project is experimental and is not affiliated with or endorsed by Morningstar Corporation.

Use it at your own risk when interfacing with battery and solar equipment.

### AI Assistance

Portions of this project were created or modified using AI-assisted tools. AI-generated suggestions may be incomplete or incorrect and must not be treated as engineering certification.

Before manufacturing or using this hardware, independently review the schematics, PCB layout, component ratings, isolation boundaries, and fabrication outputs. Appropriate electrical, thermal, safety, and regulatory testing must also be performed.
