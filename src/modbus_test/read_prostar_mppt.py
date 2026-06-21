#!/usr/bin/env python3
"""Read live Modbus RTU values from a Morningstar ProStar MPPT controller.

Default query:
    python3 read_prostar_mppt.py --port /dev/ttyUSB0

The ProStar MPPT Modbus spec lists RAM registers as PDU addresses. The default
read uses register 0x0023, vb_f, "Battery Voltage, slow filter (25s)", Float16.
Default serial settings from the spec are 9600 baud, 8 data bits, no parity,
2 stop bits, Modbus server address 1.

Meterbus hardware often echoes transmitted bytes back to the host. This script
prints serial byte traces to stderr and ignores an exact echoed copy of each
request before parsing the Modbus response.
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass


READ_HOLDING_REGISTERS = 0x03
READ_INPUT_REGISTERS = 0x04


@dataclass(frozen=True)
class Register:
    address: int
    label: str
    units: str
    data_type: str


REGISTERS: dict[str, Register] = {
    "battery_voltage": Register(0x0023, "Battery voltage, 25s filtered", "V", "f16"),
    "battery_terminal_voltage": Register(0x0012, "Battery terminal voltage", "V", "f16"),
    "battery_sense_voltage": Register(0x0017, "Battery sense voltage", "V", "f16"),
    "array_voltage": Register(0x0013, "Array voltage", "V", "f16"),
    "charge_current": Register(0x0010, "Charge current", "A", "f16"),
    "battery_current_net": Register(0x0015, "Battery current, net", "A", "f16"),
    "load_current": Register(0x0016, "Load current", "A", "f16"),
    "output_power": Register(0x003C, "Charger output power", "W", "f16"),
    "battery_temperature": Register(0x001B, "Battery temperature", "deg C", "f16"),
    "charge_state": Register(0x0021, "Charge state", "", "u16"),
}

DEFAULT_REGISTERS = ("battery_voltage",)
USEFUL_REGISTERS = (
    "battery_voltage",
    "battery_terminal_voltage",
    "array_voltage",
    "charge_current",
    "output_power",
    "battery_temperature",
    "charge_state",
)

CHARGE_STATES = {
    0: "Start",
    1: "Night check",
    2: "Disconnected",
    3: "Night",
    4: "Fault",
    5: "MPPT",
    6: "Absorption",
    7: "Float",
    8: "Equalize",
    9: "Slave",
    10: "Fixed",
}


class ModbusError(RuntimeError):
    pass


def ascii_preview(data: bytes) -> str:
    return "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in data)


def format_bytes(data: bytes) -> str:
    hex_bytes = data.hex(" ").upper() or "<none>"
    return f"{len(data)} byte(s): {hex_bytes}  |{ascii_preview(data)}|"


def print_bytes(label: str, data: bytes, enabled: bool) -> None:
    if enabled:
        print(f"{label:<16} {format_bytes(data)}", file=sys.stderr)


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def build_request(unit_id: int, function_code: int, address: int, count: int) -> bytes:
    payload = struct.pack(">BBHH", unit_id, function_code, address, count)
    crc = crc16_modbus(payload)
    return payload + struct.pack("<H", crc)


def check_response_crc(frame: bytes) -> None:
    if len(frame) < 5:
        raise ModbusError(f"Short response: {frame.hex(' ').upper()}")

    actual = int.from_bytes(frame[-2:], "little")
    expected = crc16_modbus(frame[:-2])
    if actual != expected:
        raise ModbusError(
            f"Bad response CRC: got 0x{actual:04X}, expected 0x{expected:04X}; frame={frame.hex(' ').upper()}"
        )


def expected_response_length(response: bytes) -> int | None:
    if len(response) < 2:
        return None

    if response[1] & 0x80:
        return 5

    if len(response) < 3:
        return None

    return 5 + response[2]


def read_response_ignoring_echo(ser, request: bytes, debug_bytes: bool) -> bytes:
    raw_rx = bytearray()
    echo_candidate = bytearray()
    ignored_echo = b""
    response = bytearray()

    while True:
        next_byte = ser.read(1)
        if not next_byte:
            print_bytes("RX raw", bytes(raw_rx), debug_bytes)
            print_bytes("RX echo ignored", ignored_echo, debug_bytes)
            print_bytes("RX response", bytes(response), debug_bytes)
            raise ModbusError("Timed out waiting for Modbus response")

        raw_rx.extend(next_byte)

        if not response and len(echo_candidate) < len(request):
            if next_byte[0] == request[len(echo_candidate)]:
                echo_candidate.extend(next_byte)
                if len(echo_candidate) == len(request):
                    ignored_echo = bytes(echo_candidate)
                continue

            response.extend(echo_candidate)
            echo_candidate.clear()

        response.extend(next_byte)

        response_len = expected_response_length(response)
        if response_len is not None and len(response) >= response_len:
            break

    print_bytes("RX raw", bytes(raw_rx), debug_bytes)
    print_bytes("RX echo ignored", ignored_echo, debug_bytes)
    print_bytes("RX response", bytes(response), debug_bytes)
    return bytes(response)


def read_registers(
    ser,
    unit_id: int,
    function_code: int,
    address: int,
    count: int,
    debug_bytes: bool,
) -> list[int]:
    request = build_request(unit_id, function_code, address, count)

    ser.reset_input_buffer()
    print_bytes("TX request", request, debug_bytes)
    ser.write(request)
    ser.flush()

    response = read_response_ignoring_echo(ser, request, debug_bytes)
    check_response_crc(response)

    response_unit, response_function = response[0], response[1]
    if response_unit != unit_id:
        raise ModbusError(f"Unexpected unit id {response_unit}; expected {unit_id}")

    if response_function & 0x80:
        exception_code = response[2]
        raise ModbusError(f"Modbus exception from unit {unit_id}: function 0x{function_code:02X}, code {exception_code}")

    if response_function != function_code:
        raise ModbusError(f"Unexpected function code 0x{response_function:02X}; expected 0x{function_code:02X}")

    byte_count = response[2]
    if byte_count != count * 2:
        raise ModbusError(f"Unexpected byte count {byte_count}; expected {count * 2}")

    data = response[3:-2]
    return [int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)]


def decode_register(raw: int, data_type: str) -> float | int:
    if data_type == "f16":
        return struct.unpack(">e", raw.to_bytes(2, "big"))[0]
    if data_type == "u16":
        return raw
    raise ValueError(f"Unsupported data type: {data_type}")


def format_value(name: str, register: Register, value: float | int, raw: int) -> str:
    if register.data_type == "f16":
        value_text = f"{value:.3f}".rstrip("0").rstrip(".")
    elif name == "charge_state":
        value_text = f"{value} ({CHARGE_STATES.get(int(value), 'unknown')})"
    else:
        value_text = str(value)

    units = f" {register.units}" if register.units else ""
    return f"{name}: {value_text}{units}  [0x{register.address:04X} {register.label}, raw=0x{raw:04X}]"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query Morningstar ProStar MPPT RAM registers over Modbus RTU.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--port", help="Serial device, for example /dev/ttyUSB0 or COM3.")
    parser.add_argument("--unit", type=int, default=1, help="Modbus server/slave address.")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate.")
    parser.add_argument("--timeout", type=float, default=1.0, help="Serial read timeout in seconds.")
    parser.add_argument(
        "--debug-bytes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print serial TX/RX byte traces to stderr.",
    )
    parser.add_argument(
        "--function",
        choices=("input", "holding"),
        default="input",
        help="Use function 0x04 read input registers or 0x03 read holding registers.",
    )
    parser.add_argument(
        "--register",
        action="append",
        choices=sorted(REGISTERS),
        help="Named register to read. Repeat for multiple. Defaults to battery_voltage.",
    )
    parser.add_argument("--all", action="store_true", help="Read a useful set of live values.")
    parser.add_argument("--list", action="store_true", help="List supported named registers and exit.")
    return parser.parse_args()


def import_serial():
    try:
        import serial
    except ImportError:  # pragma: no cover - only hit when dependency is missing.
        print("Missing dependency: pyserial. Install it with: python3 -m pip install pyserial", file=sys.stderr)
        raise SystemExit(2)
    return serial


def main() -> int:
    args = parse_args()

    if args.list:
        for name, register in sorted(REGISTERS.items()):
            print(f"{name}: 0x{register.address:04X} {register.data_type} {register.label} {register.units}".rstrip())
        return 0

    if not args.port:
        raise SystemExit("--port is required unless --list is used")

    if not 1 <= args.unit <= 247:
        raise SystemExit("--unit must be in Modbus address range 1..247")

    function_code = READ_INPUT_REGISTERS if args.function == "input" else READ_HOLDING_REGISTERS
    names = USEFUL_REGISTERS if args.all else tuple(args.register or DEFAULT_REGISTERS)

    serial = import_serial()
    with serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_TWO,
        timeout=args.timeout,
    ) as ser:
        for name in names:
            register = REGISTERS[name]
            raw = read_registers(ser, args.unit, function_code, register.address, 1, args.debug_bytes)[0]
            value = decode_register(raw, register.data_type)
            print(format_value(name, register, value, raw))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ModbusError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
