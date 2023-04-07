#!/usr/bin/python3
"""Configuration and status reporting for USB PWM fan devices.

See https://github.com/sparky8512/usb-pwm-fan for more detail.
"""

import abc
import argparse
import sys
import uuid

try:
    import serial
    pyserial_ok = True  # pylint: disable=invalid-name
except ModuleNotFoundError:
    # defer error in case not needed
    pyserial_ok = False  # pylint: disable=invalid-name
try:
    import libusb_package
    usb_module = libusb_package
except ModuleNotFoundError:
    try:
        import usb.core
        usb_module = usb.core
    except ModuleNotFoundError:
        sys.exit("Must install libusb-package and/or pyusb packages")

import atmega32u4_upload

DEVICE_UUID = "{1ad9f93b-494c-4dda-a1e5-2e2bab181052}"
DEVICE_MAJOR = 0
DEVICE_MINOR = 1

# NOTE: These are subject to change until DEVICE_MAJOR changes to 1
REGISTER_PWM_DUTY = 0x10
REGISTER_PWM_PERIOD = 0x11
REGISTER_TACHOMETER = 0x12
REGISTER_LED_CONTROL = 0xf1
REGISTER_RESET_CONTROL = 0xf0
REGISTER_SERIAL_NUMBER = 0xf8

LED_MODES = ("alert", "on", "off", "blink")
RESET_MODES = ("config", "reboot", "bootloader")


class FanDevice(abc.ABC):

    @abc.abstractmethod
    def read_register(self, reg, length):
        raise NotImplementedError()

    @abc.abstractmethod
    def write_register(self, reg, value):
        raise NotImplementedError()


class SerialFanDevice(FanDevice):

    def __init__(self, port):
        self._dev = serial.Serial(port, timeout=5, write_timeout=5)

    def __str__(self):
        return self._dev.name

    def read_register(self, reg, length):
        self._dev.write("R{}\n".format(reg).encode("ascii"))
        # clear out the echo
        while True:
            buf = self._dev.read(1)
            if not buf:
                return -1
            if buf[0] == ord("\n"):
                break

        data = bytearray()
        while True:
            buf = self._dev.read(1)
            if not buf:
                return -1
            if buf[0] == ord("\n"):
                break
            if buf[0] != ord("\r"):
                data.append(buf[0])

        if reg == REGISTER_SERIAL_NUMBER:
            return data.decode("ascii")
        return int(data)

    def write_register(self, reg, value):
        self._dev.write("W{},{}\n".format(reg, value).encode("ascii"))
        # clear out the echo so it doesn't sit around
        while True:
            buf = self._dev.read(1)
            if not buf or buf[0] == ord("\n"):
                break


class UsbFanDevice(FanDevice):

    def __init__(self, device, interface):
        self._dev = device
        self._iface = interface

    def __str__(self):
        return "{:04x}:{:04x} {:02x} {:3d} {:4d} {:4d} {}".format(self._dev.idVendor,
                                                                  self._dev.idProduct, self._iface,
                                                                  self._dev.bus, self._dev.address,
                                                                  self._dev.port_number,
                                                                  self._dev.serial_number)

    def read_register(self, reg, length):
        data = bytes(self._dev.ctrl_transfer(0xC1, reg, 0, self._iface, length))
        if reg == REGISTER_SERIAL_NUMBER:
            return data.decode("ascii")
        if len(data) == 2:
            return data[0] + data[1] * 256
        return data

    def write_register(self, reg, value):
        self._dev.ctrl_transfer(0x41, reg, value, self._iface, 0)


class FanDeviceRebooter:

    def __init__(self, dev):
        self._dev = dev

    def __call__(self):
        try:
            self._dev.write_register(0xf0, 3)
        except Exception as ex:
            sys.exit("Error requesting bootloader reboot: " + str(ex))


class UuidFinder:

    def __init__(self, match_uuid):
        self._uuid = uuid.UUID(match_uuid)

    def check_bos(self, buf):
        if len(buf) < 5 or buf[0] < 5 or buf[1] != 0x0f:
            return False
        end = min(len(buf), buf[2] + buf[3] * 256)
        num_caps = buf[4]
        found_cap_data = []
        pos = 5
        while num_caps:
            remain = end - pos
            if remain < 3 or buf[pos] < 3 or buf[pos + 1] != REGISTER_PWM_DUTY:
                break
            if buf[pos] > remain:
                break
            if buf[pos + 2] == 0x05 and buf[pos] >= 20:
                platform_cap_uuid = uuid.UUID(bytes_le=bytes(buf[pos + 4:pos + 20]))
                if platform_cap_uuid == self._uuid:
                    found_cap_data.append(bytes(buf[pos + 20:pos + buf[pos]]))
            pos += buf[pos]
            num_caps -= 1
        return found_cap_data

    def __call__(self, dev):
        if dev.bcdUSB < 0x0201:
            return False
        try:
            bos_descr = dev.ctrl_transfer(0x80, 6, 0x0F00, 0, 1024)
        except Exception:
            return False
        data = self.check_bos(bos_descr)
        if data:
            dev.uuid_finder_data = data
            return True
        return False


def find_fan_devs(index=None):
    fan_devs = []
    found = 0
    devs = usb_module.find(find_all=1, custom_match=UuidFinder(DEVICE_UUID))
    for dev in devs:
        for data in dev.uuid_finder_data:
            if len(data) >= 3 and data[1] == DEVICE_MAJOR and data[0] == DEVICE_MINOR:
                if index is None or index == found:
                    fan_devs.append(UsbFanDevice(dev, data[2]))
                if index == found:
                    break
            found += 1
        del dev.uuid_finder_data
    return fan_devs


def list_command(dev, opts):  # pylint: disable=unused-argument
    print(dev)


def set_command(dev, opts):
    max_duty = dev.read_register(REGISTER_PWM_PERIOD, 2)
    duty = round(max_duty * opts.speed / 100.0)
    dev.write_register(REGISTER_PWM_DUTY, duty)


def get_command(dev, opts):  # pylint: disable=unused-argument
    print(dev.read_register(REGISTER_TACHOMETER, 2))


def set_frequency_command(dev, opts):
    max_duty = round(16000000.0 / opts.freq)
    if max_duty > 0xffff:
        max_duty = 0
    dev.write_register(REGISTER_PWM_PERIOD, max_duty)


def get_frequency_command(dev, opts):  # pylint: disable=unused-argument
    max_duty = dev.read_register(REGISTER_PWM_PERIOD, 2)
    print(round(16000000.0 / max_duty, 2))


def led_command(dev, opts):
    mode = LED_MODES.index(opts.mode)
    dev.write_register(REGISTER_LED_CONTROL, mode)


def reset_command(dev, opts):
    mode = RESET_MODES.index(opts.mode) + 1
    dev.write_register(REGISTER_RESET_CONTROL, mode)


def write_register_command(dev, opts):
    dev.write_register(opts.register, opts.value)


def read_register_command(dev, opts):
    if opts.register == REGISTER_SERIAL_NUMBER:
        buflen = 20
    else:
        buflen = 2
    print(dev.read_register(opts.register, buflen))


def upload_command(dev, opts):
    reboot = FanDeviceRebooter(dev)
    atmega32u4_upload.upload_firmware(opts, reboot)


def parse_args():
    parser = argparse.ArgumentParser(description="USB fan device configuration")
    parser.add_argument("-i", "--index", type=int, help="0-based index of device to use")
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Run operation on all attached devices instead of just the first one found")
    parser.add_argument("-s",
                        "--serial-port",
                        help="Serial port to use instead of USB interface",
                        metavar="PORT")
    command_parsers = parser.add_subparsers(required=True)

    subparser = command_parsers.add_parser("list", help="List attached fan devices")
    subparser.set_defaults(command_func=list_command, header=True)

    subparser = command_parsers.add_parser("set", help="Set fan speed")
    subparser.add_argument("speed", type=float, help="Fan speed, in percent", metavar="SPEED")
    subparser.set_defaults(command_func=set_command, header=False)

    subparser = command_parsers.add_parser("get", help="Get current fan speed, in RPM")
    subparser.set_defaults(command_func=get_command, header=True)

    subparser = command_parsers.add_parser("set_frequency", help="Set PWM frequency")
    subparser.add_argument("freq", type=float, help="Frequency, in Hz", metavar="FREQ")
    subparser.set_defaults(command_func=set_frequency_command, header=False)

    subparser = command_parsers.add_parser("get_frequency", help="Get PWM frequency, in Hz")
    subparser.set_defaults(command_func=get_frequency_command, header=True)

    subparser = command_parsers.add_parser("led", help="Set LED mode")
    subparser.add_argument("mode", choices=LED_MODES, help="The mode to set")
    subparser.set_defaults(command_func=led_command, header=False)

    subparser = command_parsers.add_parser("reset", help="Reset device")
    subparser.add_argument("--mode",
                           choices=RESET_MODES,
                           default="reboot",
                           help="Reset mode to use; default is reboot")
    subparser.set_defaults(command_func=reset_command, header=False)

    subparser = command_parsers.add_parser("write_register", help="Write value to register")
    subparser.add_argument("register", type=int, help="Register number to read", metavar="REG")
    subparser.add_argument("value", help="Value or data to write", metavar="VALUE")
    subparser.set_defaults(command_func=write_register_command, header=False)

    subparser = command_parsers.add_parser("read_register", help="Read register value")
    subparser.add_argument("register", type=int, help="Register number to read", metavar="REG")
    subparser.set_defaults(command_func=read_register_command, header=True)

    subparser = command_parsers.add_parser("upload", help="Upload firmware to device")
    atmega32u4_upload.argparse_core_args(subparser)
    subparser.set_defaults(command_func=upload_command, header=False)

    opts = parser.parse_args()

    if opts.serial_port is not None:
        if not pyserial_ok:
            parser.error("--serial-port option requires pyserial package to be installed")
        if opts.all or opts.index is not None:
            parser.error("--serial-port may not be combined with --all or --index")
    if opts.all and opts.index is not None:
        parser.error("--all may not be combined with --index")
    if not opts.all and opts.index is None and opts.command_func != list_command:  # pylint: disable=comparison-with-callable
        opts.index = 0
    if opts.command_func == set_command and (opts.speed < 0.0 or opts.speed > 100.0):  # pylint: disable=comparison-with-callable
        parser.error("Invalid speed percentage")
    if opts.command_func == write_register_command and opts.register != REGISTER_SERIAL_NUMBER:  # pylint: disable=comparison-with-callable
        try:
            opts.value = int(opts.value)
        except ValueError:
            parser.error("Register {} requires an int value".format(opts.register))
    if opts.command_func == upload_command:  # pylint: disable=comparison-with-callable
        atmega32u4_upload.check_core_args(opts, parser.error)

    return opts


def main():
    opts = parse_args()
    if opts.serial_port is not None:
        try:
            dev = SerialFanDevice(opts.serial_port)
        except serial.SerialException as ex:
            sys.exit("Error opening serial port: " + str(ex))
        opts.command_func(dev, opts)
    else:
        devs = find_fan_devs(index=opts.index)
        if not devs:
            print("No USB fan device found")
        elif len(devs) == 1 and not opts.all and opts.command_func != list_command:  # pylint: disable=comparison-with-callable
            opts.command_func(devs[0], opts)
        else:
            if opts.header:
                print(" VID  PID IF Bus Addr Port SerialNumber")
            for dev in devs:
                if opts.header and opts.command_func != list_command:  # pylint: disable=comparison-with-callable
                    print("{!s:<47}: ".format(dev), end="")
                opts.command_func(dev, opts)

    sys.exit(0)


if __name__ == "__main__":
    main()
