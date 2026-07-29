# MeterBus Observations

This document describes observations and measurements of the Morningstar MeterBus interface.

Morningstar MeterBus is a single-wire open-collector style serial bus exposed on an RJ11 connector.

## Power Supply

The Morningstar controllers supply some power via the RJ11 interface.

### Voltage

When testing the supply from a ProStar MPPT controller, the voltage appeared to be regulated to a maximum of 11.9VDC, but fell as the battery voltage dropped below 12.9VDC. Similar testing with a SunSaver MPPT controller seemed to show the output was regulated to about 14VDC. Battery voltage for the testing ranged from 5VDC up to and above 24VDC.

These observations fit within the range of 8VDC - 15.5VDC specified by Morningstar in [`Meterbus Adapter Instructions`](./docs/operation-manual-pc-meterbus-adapter-en.pdf).

All power pins on the RJ11 connector appear to be bridged together, as do the ground pins.

### Current

Observed load-test results for the nominal 12 V supply:

| Load resistor | Measured voltage | Calculated current |
| ------------: | ---------------: | -----------------: |
|  Open circuit |           12.4 V |               0 mA |
|         150 Ω |            8.4 V |              56 mA |
|          67 Ω |            4.2 V |            62.7 mA |
|          33 Ω |            2.4 V |            72.7 mA |
|          0 Ω |            0 V |            13 mA |

Overall, the supply voltage sags heavily under load, while current rises into roughly the **55–75 mA** range over these tests.

## MeterBus

Measurements of the bus pin on both ProStar MPPT and SunSaver MPPT controllers show that the bus idles high at about 7.5VDC, and is pulled down to 0VDC when the controller transmits. The bus is a half-duplex serial line running at 9600 baud, with 8 data bits, 2 stop bits and no parity. 

The bus is weakly pulled up, and has a short circuit current to ground of about 700-800uA for both controllers

If we assume that the bus is pulled to an internal rail of 7.5VDC with a resistor, Ohms Law `7.5V/850uA=10kOhm` says the internal resistor is 10kOhms.

### Low Level Threshold

In order to figure out what bus voltage the controllers consider as a logic LOW, we tested several values of **R** in the test circuit pictured below while probing the bus with an oscilloscope.

![Bus test circuit](/image/bus_drive_resistors/test_circuit.png)

The oscilloscope traces can be found in [this folder](/image/bus_drive_resistors). The first block of data in the traces is the test circuit requesting the controller voltage over modbus, and the second block is the controller responding. Traces only show the first block of data when the controller did not respond.

The results showed that the controller stopped responding consistently at around 2.733kOhm, when the LOW level was around 1.3VDC.

The observed voltages also roughly match a voltage divider with the top resistor being 10kOhms, which seems to confirm that the controller probably has a 10kOhm pullup resistor internally.