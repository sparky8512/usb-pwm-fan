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

DESCRIPTOR_TYPE_BOS = 0x0f
DESCRIPTOR_TYPE_DEVICE_CAPABILITY = 0x10
CAPABILITY_TYPE_PLATFORM = 0x05

DEVICE_UUID = "{1ad9f93b-494c-4dda-a1e5-2e2bab181052}"
DEVICE_MAJOR = 1
DEVICE_MINOR = 0

REGISTER_PWM_DUTY1 = 0x10
REGISTER_PWM_PERIOD = 0x11
REGISTER_TACHOMETER1 = 0x12
REGISTER_PWM_DUTY2 = 0x20
REGISTER_TACHOMETER2 = 0x22
REGISTER_PWM_DUTY3 = 0x30
REGISTER_TACHOMETER3 = 0x32
REGISTER_RESET_CONTROL = 0xf0
REGISTER_LED_CONTROL = 0xf1
REGISTER_CONFIG_CONTROL = 0xf2
REGISTER_SERIAL_NUMBER = 0xf8

LED_MODES = ("alert", "on", "off", "blink")
"""Valid modes for `FanDevice.set_led_mode`"""
RESET_MODES = ("config", "reboot", "bootloader", "factory")
"""Valid modes for `FanDevice.reset`"""


class FanDevice(abc.ABC):
    """Interface for operating on a USB fan device."""

    @abc.abstractmethod
    def read_register(self, reg, length):
        raise NotImplementedError()

    @abc.abstractmethod
    def write_register(self, reg, value):
        raise NotImplementedError()

    @abc.abstractmethod
    def version_ok(self):
        raise NotImplementedError()

    def set_speed(self, speed, index):
        """Set fan speed (PWM duty cycle).

        Args:
            speed (float): Speed, in percent.
            index (int): Index of fan to use.
        """
        max_duty = self.read_register(REGISTER_PWM_PERIOD, 2)
        duty = round(max_duty * speed / 100.0)
        self.write_register(REGISTER_PWM_DUTY1 + index * 0x10, duty)

    def get_speed(self, index):
        """Get fan speed.

        Args:
            index (int): Index of fan to use.

        Returns:
            A float denoting the rotational speed, in RPM.
        """
        return self.read_register(REGISTER_TACHOMETER1 + index * 0x10, 2)

    def set_frequency(self, freq):
        """Set PWM frequency, in Hz."""
        max_duty = round(16000000.0 / freq)
        if max_duty > 0xffff:
            max_duty = 0
        self.write_register(REGISTER_PWM_PERIOD, max_duty)

    def get_frequency(self):
        """Get PWM frequency, in Hz."""
        max_duty = self.read_register(REGISTER_PWM_PERIOD, 2)
        return round(16000000.0 / max_duty, 2)

    def set_led_mode(self, mode):
        """Set LED mode.

        Args:
            mode (str): One of the modes in `LED_MODES`.
        """
        self.write_register(REGISTER_LED_CONTROL, LED_MODES.index(mode))

    def save_config(self):
        """Save current configuration as power-on defaults."""
        self.write_register(REGISTER_CONFIG_CONTROL, 1)

    def reset(self, mode):
        """Reset device.

        Args:
            mode (str): One of the modes in `RESET_MODES`.
        """
        self.write_register(REGISTER_RESET_CONTROL, RESET_MODES.index(mode) + 1)


class SerialFanDevice(FanDevice):
    """Serial port control of a USB fan device."""

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

    def version_ok(self):
        return True


class UsbFanDevice(FanDevice):
    """Direct USB control of a USB fan device."""

    def __init__(self, device, interface, major, minor):
        self._dev = device
        self._iface = interface
        self._version_major = major
        self._version_minor = minor

    def _version_str(self):
        return "{}.{}".format(self._version_major, self._version_minor)

    def __str__(self):
        return "{:04x}:{:04x} {:02x} {:3d} {:4d} {:4d} {:>5} {}".format(
            self._dev.idVendor, self._dev.idProduct, self._iface, self._dev.bus, self._dev.address,
            self._dev.port_number, self._version_str(), self._dev.serial_number)

    def read_register(self, reg, length):
        data = bytes(self._dev.ctrl_transfer(0xC1, reg, 0, self._iface, length))
        if reg == REGISTER_SERIAL_NUMBER:
            return data.decode("ascii")
        if len(data) == 2:
            return data[0] + data[1] * 256
        return data

    def write_register(self, reg, value):
        self._dev.ctrl_transfer(0x41, reg, value, self._iface, 0)

    def version_ok(self):
        if self._version_major != DEVICE_MAJOR:
            print("Device '{}' interface version major mismatch: {} vs {}.{}; "
                  "firmware needs update.".format(self._dev.serial_number, self._version_str(),
                                                  DEVICE_MAJOR, DEVICE_MINOR))
            return False
        if self._version_minor < DEVICE_MINOR:
            print("Device '{}' interface version minor insufficient: {} < {}.{}; "
                  "firmware needs update.".format(self._dev.serial_number, self._version_str(),
                                                  DEVICE_MAJOR, DEVICE_MINOR))
            return False
        return True


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
        if len(buf) < 5 or buf[0] < 5 or buf[1] != DESCRIPTOR_TYPE_BOS:
            return False
        end = min(len(buf), buf[2] + buf[3] * 256)
        num_caps = buf[4]
        found_cap_data = []
        pos = 5
        while num_caps:
            remain = end - pos
            if remain < 3 or buf[pos] < 3 or buf[pos + 1] != DESCRIPTOR_TYPE_DEVICE_CAPABILITY:
                break
            if buf[pos] > remain:
                break
            if buf[pos + 2] == CAPABILITY_TYPE_PLATFORM and buf[pos] >= 20:
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
            if len(data) >= 3:
                if index is None or index == found:
                    fan_devs.append(UsbFanDevice(dev, data[2], data[1], data[0]))
                if index == found:
                    break
            found += 1
        del dev.uuid_finder_data
    return fan_devs


def list_command(dev, opts):  # pylint: disable=unused-argument
    print(dev)


def set_command(dev, opts):
    dev.set_speed(opts.speed, opts.fan_index)


def get_command(dev, opts):  # pylint: disable=unused-argument
    print(dev.get_speed(opts.fan_index))


def set_frequency_command(dev, opts):
    dev.set_frequency(opts.freq)


def get_frequency_command(dev, opts):  # pylint: disable=unused-argument
    print(dev.get_frequency())


def led_command(dev, opts):
    dev.set_led_mode(opts.mode)


def save_command(dev, opts):  # pylint: disable=unused-argument
    dev.save_config()


def reset_command(dev, opts):
    dev.reset(opts.mode)


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
    parser.add_argument("-f",
                        "--fan-index",
                        type=int,
                        default=0,
                        help="0-based index of fan to use on device; default is 0")
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
    subparser.set_defaults(command_func=list_command, header=True, version_check=False)

    subparser = command_parsers.add_parser("set", help="Set fan speed")
    subparser.add_argument("speed", type=float, help="Fan speed, in percent", metavar="SPEED")
    subparser.set_defaults(command_func=set_command, header=False, version_check=True)

    subparser = command_parsers.add_parser("get", help="Get current fan speed, in RPM")
    subparser.set_defaults(command_func=get_command, header=True, version_check=True)

    subparser = command_parsers.add_parser("set_frequency", help="Set PWM frequency")
    subparser.add_argument("freq", type=float, help="Frequency, in Hz", metavar="FREQ")
    subparser.set_defaults(command_func=set_frequency_command, header=False, version_check=True)

    subparser = command_parsers.add_parser("get_frequency", help="Get PWM frequency, in Hz")
    subparser.set_defaults(command_func=get_frequency_command, header=True, version_check=True)

    subparser = command_parsers.add_parser("led", help="Set LED mode")
    subparser.add_argument("mode", choices=LED_MODES, help="The mode to set")
    subparser.set_defaults(command_func=led_command, header=False, version_check=True)

    subparser = command_parsers.add_parser("save", help="Persist configuration across device reset")
    subparser.set_defaults(command_func=save_command, header=False, version_check=True)

    subparser = command_parsers.add_parser("reset", help="Reset device")
    subparser.add_argument("--mode",
                           choices=RESET_MODES,
                           default="reboot",
                           help="Reset mode to use; default is reboot")
    subparser.set_defaults(command_func=reset_command, header=False, version_check=True)

    subparser = command_parsers.add_parser("write_register", help="Write value to register")
    subparser.add_argument("register", type=int, help="Register number to write", metavar="REG")
    subparser.add_argument("value", help="Value or data to write", metavar="VALUE")
    subparser.set_defaults(command_func=write_register_command, header=False, version_check=False)

    subparser = command_parsers.add_parser("read_register", help="Read register value")
    subparser.add_argument("register", type=int, help="Register number to read", metavar="REG")
    subparser.set_defaults(command_func=read_register_command, header=True, version_check=False)

    subparser = command_parsers.add_parser("upload", help="Upload firmware to device")
    atmega32u4_upload.argparse_core_args(subparser)
    subparser.set_defaults(command_func=upload_command, header=False, version_check=False)

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
    if opts.fan_index < 0 or opts.fan_index > 2:
        parser.error("Fan index must be between 0 and 2")
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

        def check_and_run(dev, opts):
            if opts.version_check:
                if not dev.version_ok():
                    # output is done in version_ok
                    return
            opts.command_func(dev, opts)

        devs = find_fan_devs(index=opts.index)
        if not devs:
            print("No USB fan device found")
        elif len(devs) == 1 and not opts.all and opts.command_func != list_command:  # pylint: disable=comparison-with-callable
            check_and_run(devs[0], opts)
        else:
            if opts.header:
                print(" VID  PID IF Bus Addr Port IfVer SerialNumber")
            for dev in devs:
                if opts.header and opts.command_func != list_command:  # pylint: disable=comparison-with-callable
                    print("{!s:<47}: ".format(dev), end="")
                check_and_run(dev, opts)

    sys.exit(0)


if __name__ == "__main__":
    main()
