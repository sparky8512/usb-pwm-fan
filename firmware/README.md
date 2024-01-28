# usb-pwm-fan firmware

This directory contains the source code for the USB device firmware for this project. It uses the [AVR Arduino core](https://github.com/arduino/ArduinoCore-avr) and can be built using [PlatformIO](https://platformio.org/).

## Configuration file

If you need to change anything in the build configuration, you can do so in the file [platformio.ini](platformio.ini). Adding support for a different Atmega32U4-based board that is supported by PlatformIO should be as simple as adding a new `[env:<NAME>]` section and setting its `board` to the appropriate PlatformIO board type. If you need to override `build_flags`, though, make sure to include the `-DUSB_VERSION=0x210` bit, as that setting will replace the previously set flags, not add to it.

See the [PlatformIO docs](https://docs.platformio.org/en/latest/projectconf/index.html) for the full reference on the format of that file.

## Building from source

The source code should be buildable on any host that PlatformIO can run on. If you don't already have it installed, install the PlatformIO CLI tools by following [the PlatformIO installation instructions](https://docs.platformio.org/en/latest/core/installation/methods/index.html). Make sure the `pio` command is in your PATH (see [here](https://docs.platformio.org/en/latest/core/installation/shell-commands.html#piocore-install-shell-commands) if you need help with that).

To build all configured board variants:
```shell script
pio run
```

To program the built firmware into an attached USB device:
```shell script
pio run -v --target upload --environment <ENVIRONMENT> --upload-port <PORT>
```
Where `<ENVIRONMENT>` is one of the board type specific build environments configured in [platformio.ini](platformio.ini) and `<PORT>` is the device name of the USB serial port the device shows up as on your system, such as `COM6` or `/dev/ttyUSB0`.

Or you could use the [atmega32u4\_upload.py](../util/atmega32u4_upload.py) script from this project. Run it with `--help` option for full usage details. You can find the built firmware files at `.pio/build/<ENVIRONMENT>/firmware.hex` relative to this directory.
