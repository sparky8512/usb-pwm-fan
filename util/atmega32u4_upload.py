#!/usr/bin/python3
"""Firmware upload for Atmel (Microchip) ATmega32U4 microcontroller

Mostly just a wrapper around AVRDUDE. Assumes the microcontroller is running
the usual Caterina bootloader.
"""

import argparse
import shutil
import subprocess
import sys
import time

import serial
from serial.tools import list_ports

DEFAULT_TIMEOUT = 10.0


class SerialRebooter:

    def __init__(self, port):
        self._port = port

    def __call__(self):
        try:
            dev = serial.Serial(self._port, baudrate=1200)
            dev.close()
        except serial.SerialException as ex:
            sys.exit("Error opening serial port: " + str(ex))


def manual_reboot():
    print("Manually reboot your device now. Ctrl-C to exit.")


def find_by_serial_number(serial_number):
    for port in list_ports.comports():
        if port.hwid.startswith("USB") and port.serial_number == serial_number:
            return port.device
    return None


def get_bootloader_port(reboot, timeout):
    before = set()
    for port in list_ports.comports():
        if port.hwid.startswith("USB"):
            before.add((port.device, port.hwid))
    print("Waiting for bootloader port")
    reboot()
    start_time = time.monotonic()
    while True:
        after = set()
        for port in list_ports.comports():
            if port.hwid.startswith("USB"):
                # Check for USB serial device with new port device
                # or different hardware details (VID/PID, etc)
                port_info = (port.device, port.hwid)
                if port_info in before:
                    after.add(port_info)
                else:
                    return port.device
        before = after
        if timeout is not None and time.monotonic() > start_time + timeout:
            return None
        time.sleep(0.1)


def upload_firmware(opts, reboot):
    if not hasattr(opts, "bootloader_port") or opts.bootloader_port is None:
        try:
            port = get_bootloader_port(reboot, opts.timeout)
        except KeyboardInterrupt:
            return 1
        if port is None:
            sys.exit("Timed out waiting for bootloader port")
    else:
        port = opts.bootloader_port
    avrdude_args = [opts.avrdude]
    if opts.verbose:
        avrdude_args.append("-v")
    if opts.dry_run:
        avrdude_args.append("-n")
    if opts.avrdude_conf is not None:
        avrdude_args.extend(["-C", opts.avrdude_conf])
    avrdude_args.extend([
        "-p", "atmega32u4", "-c", "avr109", "-D", "-P", port, "-U", "flash:w:{}:i".format(opts.file)
    ])
    comp = subprocess.run(avrdude_args)
    return comp.returncode


# These are shared with other users of the upload_firmware function
def argparse_core_args(parser):
    parser.add_argument("file", help="Path to .hex file to upload", metavar="HEX_FILE")
    parser.add_argument("-a", "--avrdude", help="Path to avrdude executable", metavar="PATH")
    parser.add_argument("-c", "--avrdude-conf", help="Path to avrdude conf file", metavar="PATH")
    parser.add_argument("-n",
                        "--dry-run",
                        action="store_true",
                        help="Don't actually write the firmware")
    parser.add_argument("-t",
                        "--timeout",
                        type=int,
                        help="Max time to wait for bootloader serial port, in seconds")
    parser.add_argument("-v", "--verbose", action="store_true", help="Be verbose")


def check_core_args(opts, error):
    if opts.avrdude is None:
        opts.avrdude = shutil.which("avrdude")
    if opts.avrdude is None:
        error("avrdude not found in PATH, use --avrdude option to specify location")


def parse_args():
    parser = argparse.ArgumentParser(description="ATmega32U4 firmware upload")
    argparse_core_args(parser)
    parser.add_argument("-b",
                        "--bootloader-port",
                        help="Use specified bootloader port instead of rebooting device and auto-"
                        "detecting it",
                        metavar="PORT")
    parser.add_argument("-m",
                        "--manual-reboot",
                        action="store_true",
                        help="Prompt user to manually reboot when ready")
    parser.add_argument("-p",
                        "--port",
                        help="Serial port of device to use for reboot; this is the port assigned "
                        "when running application (sketch), not the one assigned to the bootloader")
    parser.add_argument("-s",
                        "--serial-number",
                        help="Find serial port by USB device serial number")

    opts = parser.parse_args()
    check_core_args(opts, parser.error)
    if (opts.bootloader_port is not None) + (opts.port is not None) + (
            opts.serial_number is not None) + opts.manual_reboot != 1:
        parser.error("Exactly one of --bootloader-port, --manual-reboot, --port, or "
                     "--serial-number must be specified")
    if not opts.manual_reboot and opts.timeout is None:
        opts.timeout = DEFAULT_TIMEOUT
    if opts.serial_number is not None:
        opts.port = find_by_serial_number(opts.serial_number)
        if opts.port is None:
            parser.error("No USB serial device with serial number {} found".format(
                opts.serial_number))

    return opts


def main():
    opts = parse_args()

    if opts.manual_reboot:
        reboot = manual_reboot
    else:
        reboot = SerialRebooter(opts.port)
    rval = upload_firmware(opts, reboot)

    sys.exit(rval)


if __name__ == "__main__":
    main()
