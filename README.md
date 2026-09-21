# EveningStar Hardware

<p align="center">
  <img src="https://github.com/ciaassured/eveningstar-hardware/releases/latest/download/EveningStar-turntable.webp" alt="Rotating 3D render of the EveningStar PCB" width="480">
</p>

EveningStar is a gateway between a Morningstar MeterBus network and a standard Ethernet/IP network. It connects to the MeterBus port of a Morningstar solar charge controller or other compatible device, making the bus accessible over Ethernet for monitoring, automation, and control.

The hardware is built around an ESP32-C6 and divided into two galvanically isolated sections:

* A MeterBus interface, powered from the connected Morningstar device.
* An ESP32 and Ethernet interface, powered from its own DC input.

This isolation keeps the MeterBus network and the Morningstar device's ground separate from the rest of the system, which prevents ground loops through the MeterBus cable and stops fault currents from flowing across it. The ESP32 side can be powered from the same battery system as the charge controller or from a separate supply, even when the two operate at different voltages.

MeterBus communication is half-duplex and open-drain. The interface includes a Schmitt-trigger receive path and transient-voltage-suppression clamps to improve reliability when cables are routed through electrically noisy environments.

## Specifications

| | |
| --- | --- |
| Processor | ESP32-C6-WROOM-1-N8 module: Wi-Fi 6, Bluetooth LE, and IEEE 802.15.4, with 8 MB flash and an on-board antenna |
| Storage | 256 MB SPI NAND flash (GD5F2GM7) |
| Real-time clock | 32.768 kHz crystal |
| Ethernet | 10/100 Mbit/s, WIZnet W5500 with a hardware TCP/IP stack, RJ45 jack with integrated magnetics |
| MeterBus | RJ11 (6P6C) jack to the Morningstar MeterBus port |
| USB | USB-C for firmware flashing and console access only; it does not power the board |
| Debug | Unpopulated header for an ESP-Prog debugger |
| Power input | 8–40 V DC through a 3.81 mm pluggable terminal block, ESP32 side |
| MeterBus supply | Powered by the Morningstar device through the MeterBus port, up to the 15.5 V Morningstar specifies, MeterBus side |
| Isolation | ISO6721 digital isolator between the two sides, rated 3000 V rms withstand and 450 V rms working voltage (basic isolation, UL 1577); only data crosses it |
| Operating temperature | −30 °C to +85 °C, from component ratings |
| Board size | 81.2 × 71.6 mm |

## Protection

* **Power input:** a 1 A very-fast-acting fuse, a series Schottky diode against reverse polarity, and a 40 V TVS diode that clamps surges. The TVS diode sets the 40 V upper limit, well within the 80 V rating of the LMR38020S converter behind it.
* **Brown-out:** the ESP32 is held in reset until the converter reports that the 3.3 V rail is in regulation.
* **MeterBus:** galvanic isolation, since the MeterBus side is powered by the Morningstar device and shares no power or ground with the rest of the board. Its supply has a series Schottky diode against reverse polarity and a 17 V TVS diode, and the data line has a TVS clamp for positive and negative spikes.
* **USB:** ESD protection on the data lines. VBUS is not connected to any power rail, so the board cannot draw power from USB or feed power back into it.
* **Ethernet:** the jack's integrated magnetics transformer-couple the data pairs, and its shield is connected to ground only through a 1 nF, 2 kV capacitor, so the Ethernet cable carries no DC ground current.

The ratings above come from component datasheets. The board has not been independently tested or certified for isolation, surge immunity, or its temperature range.

## Installation

* **Power:** connect 8–40 V DC to the terminal block, observing the + and − markings beside it. Fuse the positive supply with a 1 A fuse close to the power source, and use wiring rated to carry at least 1 A continuously. The 1 A fuse on the board protects the board itself; the fuse at the source protects the wiring between them, so choose one that is rated for the supply's DC voltage and can break the current a battery can deliver into a short.
* **MeterBus:** connect the RJ11 jack to the Morningstar device's MeterBus port. The MeterBus side takes its power from that port.
* **Ethernet:** connect a standard Ethernet cable. The board is not powered over Ethernet.

> [!WARNING]
> Do not leave USB connected while the system is in service. USB ground is connected directly to the power input's negative terminal, so a connected USB host that is grounded elsewhere creates a second ground path. Current can then flow through the board's unfused ground and the USB cable, which can damage equipment or start a fire. Use USB only for flashing or debugging, and disconnect it afterwards.

## Resources

* Schematics, board drawings, 3D models, renders, and JLCPCB production files for the current hardware revision are attached to the [latest release](https://github.com/ciaassured/eveningstar-hardware/releases/latest).
* To order assembled boards, follow [`docs/jlcpcb_order.md`](docs/jlcpcb_order.md).
* Firmware is maintained separately in the [eveningstar-firmware](https://github.com/ciaassured/eveningstar-firmware) repository.
* The KiCad project and its build, review, and fabrication workflow are documented in [`pcb/README.md`](pcb/README.md).

## Disclaimer

This project is experimental and is not affiliated with or endorsed by Morningstar Corporation.

Use it at your own risk when interfacing with battery and solar equipment.

### AI Assistance

Portions of this project were created or modified using AI-assisted tools. AI-generated suggestions may be incomplete or incorrect and must not be treated as engineering certification.

Before manufacturing or using this hardware, independently review the schematics, PCB layout, component ratings, isolation boundaries, and fabrication outputs. Appropriate electrical, thermal, safety, and regulatory testing must also be performed.
