# MorningStar MeterBus ESP32 Interface

An isolated ESP32-based interface for communicating with Morningstar solar charge controllers over the Morningstar MeterBus RJ11 interface.

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

## Disclaimer

This project is experimental and not affiliated with or endorsed by Morningstar Corporation.

Use at your own risk when interfacing with battery and solar equipment.
