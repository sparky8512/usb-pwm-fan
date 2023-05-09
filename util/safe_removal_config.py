"""Windows-specific tool for configuring USB device safe removal requirement

This tool allows for the removal of USB Fan devices from the "Safely Remove
Hardware and Eject Media" menu (the tray icon that looks like a USB plug) on
Windows.

USB Fan uses the WinUSB driver, so it doesn't require any special installation
in order to work on modern Windows OS versions. Unfortunately, the WinUSB
driver always marks its devices as not OK for "surprise removal", and there
does not appear to be any .INF file setting or simple registry entry that can
make it do otherwise. There is, however, a way to override that flag via the
Windows Setup API. This would normally be done by a device's install program,
but most WinUSB devices don't have a dedicated installer, and USB Fan doesn't
use an installer at all, since the OS can automatically configure it.

This script can serve the purpose of that bit of the installer. It can set,
remove, or get the state of that override flag for either an individual USB Fan
device, or all the attached ones. Use the --help option for full usage info.

Note that setting or removing the override flag requires running as
Administrator.

It can also be used for other USB devices that use the WinUSB driver, by using
the --guid option to specify the device interface GUID. For non-composite
devices that don't register their own interface GUID, you can use the generic
USB device interface GUID the USB hub driver registers for its direct child
devices: a5dcbf10-6530-11d2-901f-00c04fb951ed

Individual devices are identified by serial number. For devices that do not
provide a serial number, Windows will make one up based on what USB port the
device is plugged into. As such, you will need to repeat the configuration for
each new port such devices are plugged into.
"""
import argparse
import ctypes
import sys
import uuid

setupapi = ctypes.windll.setupapi

setupapi.SetupDiCreateDeviceInfoList.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
setupapi.SetupDiCreateDeviceInfoList.restype = ctypes.c_void_p

setupapi.SetupDiGetClassDevsExW.argtypes = [
    ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
    ctypes.c_wchar_p, ctypes.c_void_p
]
setupapi.SetupDiGetClassDevsExW.restype = ctypes.c_void_p

setupapi.SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p]

setupapi.SetupDiGetDevicePropertyW.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p, ctypes.c_uint,
    ctypes.POINTER(ctypes.c_uint), ctypes.c_uint
]

setupapi.SetupDiSetDevicePropertyW.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
    ctypes.c_uint, ctypes.c_uint
]

setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

INVALID_HANDLE = -1
ERROR_ACCESS_DENIED = 0x5
ERROR_INSUFFICIENT_BUFFER = 0x7a
ERROR_NO_MORE_ITEMS = 0x103
ERROR_NOT_FOUND = 0x490

WINUSB_CLASS_GUID = uuid.UUID("88bae032-5a81-49f0-bc3d-a4ff138216d6").bytes_le
USBFAN_IFACE_GUID = uuid.UUID("1ad9f93b-494c-4dda-a1e5-2e2bab181052").bytes_le


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = (
        ("cbSize", ctypes.c_uint),
        ("ClassGuid", ctypes.c_ubyte * 16),
        ("DevInst", ctypes.c_uint),
        ("Reserved", ctypes.c_void_p),
    )


class DEVPROPKEY(ctypes.Structure):
    _fields_ = (
        ("fmtid", ctypes.c_ubyte * 16),
        ("pid", ctypes.c_ulong),
    )

    def __init__(self, guid, pid):
        self.fmtid[:] = uuid.UUID(guid).bytes_le
        self.pid = pid


# from Devpropdef.h
DEVPROP_TYPE_BOOLEAN = 0x11
DEVPROP_TYPE_EMPTY = 0x0
# from Devpkey.h
DEVPKEY_Device_InstanceId = DEVPROPKEY("78c34fc8-104a-4aca-9ea4-524d52996e57", 256)
DEVPKEY_Device_Parent = DEVPROPKEY("4340a6c5-93fa-4706-972c-7b648008a5a7", 8)
DEVPKEY_Device_SafeRemovalRequiredOverride = DEVPROPKEY("afd97640-86a3-4210-b67c-289c41aabe55", 3)


def get_property(h_devinfo, p_di_data, p_key):
    proptype = ctypes.c_ulong()
    req_size = ctypes.c_uint()
    rv = setupapi.SetupDiGetDevicePropertyW(h_devinfo, p_di_data, p_key, ctypes.byref(proptype),
                                            None, 0, ctypes.byref(req_size), 0)
    if rv:
        return bytes()
    if ctypes.GetLastError() == ERROR_NOT_FOUND:
        return None
    if ctypes.GetLastError() != ERROR_INSUFFICIENT_BUFFER:
        raise ctypes.WinError()
    buff = ctypes.create_string_buffer(req_size.value)
    rv = setupapi.SetupDiGetDevicePropertyW(h_devinfo, p_di_data, p_key, ctypes.byref(proptype),
                                            ctypes.byref(buff), req_size, None, 0)
    if not rv:
        raise ctypes.WinError()
    return buff.raw


def list_command(serial_number, h_devinfo, p_di_data, opts):
    print(serial_number)


def get_command(serial_number, h_devinfo, p_di_data, opts):
    oride = get_property(h_devinfo, p_di_data,
                         ctypes.byref(DEVPKEY_Device_SafeRemovalRequiredOverride))
    print(serial_number, ": ", "<unset>" if oride is None else bool(oride[0]), sep="")


def set_command(serial_number, h_devinfo, p_di_data, opts):
    proptype = ctypes.c_ulong(DEVPROP_TYPE_BOOLEAN)
    buff = ctypes.c_ubyte(-1 if opts.value else 0)
    rv = setupapi.SetupDiSetDevicePropertyW(
        h_devinfo, p_di_data, ctypes.byref(DEVPKEY_Device_SafeRemovalRequiredOverride), proptype,
        ctypes.byref(buff), 1, 0)
    if not rv:
        if ctypes.GetLastError() == ERROR_ACCESS_DENIED:
            print("This command requires Administrator permission", file=sys.stderr)
        raise ctypes.WinError()


def remove_command(serial_number, h_devinfo, p_di_data, opts):
    proptype = ctypes.c_ulong(DEVPROP_TYPE_EMPTY)
    rv = setupapi.SetupDiSetDevicePropertyW(
        h_devinfo, p_di_data, ctypes.byref(DEVPKEY_Device_SafeRemovalRequiredOverride), proptype,
        None, 0, 0)
    if not rv:
        if ctypes.GetLastError() == ERROR_ACCESS_DENIED:
            print("This command requires Administrator permission", file=sys.stderr)
        raise ctypes.WinError()


def parse_args():
    parser = argparse.ArgumentParser(description="Windows USB device removal safety configuration")
    parser.add_argument("-g",
                        "--guid",
                        help="Device interface GUID to use instead of the USB Fan one")
    parser.add_argument(
        "-s",
        "--serial-number",
        help="Serial number of device to configure instead of configuring all devices")
    command_parsers = parser.add_subparsers(required=True)

    subparser = command_parsers.add_parser("list", help="List device serial numbers")
    subparser.set_defaults(command_func=list_command)

    subparser = command_parsers.add_parser("get", help="Get current override configuration")
    subparser.set_defaults(command_func=get_command)

    subparser = command_parsers.add_parser("set", help="Set override configuration")
    subparser.add_argument(
        "value",
        help="Boolean value to set; use false to remove device(s) from Safely Remove Hardware menu",
        metavar="VALUE")
    subparser.set_defaults(command_func=set_command)

    subparser = command_parsers.add_parser("remove", help="Remove override configuration")
    subparser.set_defaults(command_func=remove_command)

    opts = parser.parse_args()
    try:
        value = opts.value.lower()
        if value in ("y", "yes", "t", "true", "on", "1"):
            opts.value = True
        elif value in ("n", "no", "f", "false", "off", "0"):
            opts.value = False
        else:
            parser.error("Bad boolean value: " + opts.value)
    except AttributeError:
        pass
    if opts.guid:
        try:
            opts.guid = uuid.UUID(opts.guid).bytes_le
        except ValueError:
            parser.error("Bad GUID string: " + opts.guid)

    return opts


def main():
    opts = parse_args()

    h_devinfo = setupapi.SetupDiCreateDeviceInfoList(WINUSB_CLASS_GUID, None)
    if h_devinfo == INVALID_HANDLE:
        raise ctypes.WinError()
    try:
        # DIGCF_PRESENT | DIGCF_DEVICEINTERFACE == 0x12
        iface_guid = opts.guid or USBFAN_IFACE_GUID
        h_devinfo2 = setupapi.SetupDiGetClassDevsExW(iface_guid, None, None, 0x12, h_devinfo, None,
                                                     None)
        if h_devinfo2 == INVALID_HANDLE:
            raise ctypes.WinError()
        # in success case, h_devinfo2 == h_devinfo
        i = 0
        di_data = SP_DEVINFO_DATA()
        di_data.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        found = False
        while True:
            if not setupapi.SetupDiEnumDeviceInfo(h_devinfo, i, ctypes.byref(di_data)):
                if ctypes.GetLastError() != ERROR_NO_MORE_ITEMS:
                    raise ctypes.WinError()
                break
            instance = get_property(h_devinfo, ctypes.byref(di_data),
                                    ctypes.byref(DEVPKEY_Device_InstanceId))
            parent = get_property(h_devinfo, ctypes.byref(di_data),
                                  ctypes.byref(DEVPKEY_Device_Parent))
            instance_path, sep, instance_serno = instance.decode("utf-16").strip("\0").rpartition(
                "\\")
            parent_path, sep, parent_serno = parent.decode("utf-16").strip("\0").rpartition("\\")
            serial_number = parent_serno if instance_path.startswith(
                parent_path) else instance_serno
            if opts.serial_number is None or serial_number == opts.serial_number:
                opts.command_func(serial_number, h_devinfo, ctypes.byref(di_data), opts)
                found = True
            i += 1
        if opts.serial_number is not None and not found:
            print("No device found with serial number", opts.serial_number)
    except OSError as ex:
        print(ex, file=sys.stderr)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(h_devinfo)


if __name__ == "__main__":
    main()
