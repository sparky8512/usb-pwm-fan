# usb-pwm-fan

![firmware build](https://github.com/sparky8512/usb-pwm-fan/actions/workflows/firmware_build.yml/badge.svg)
![plugin build](https://github.com/sparky8512/usb-pwm-fan/actions/workflows/plugin_build.yml/badge.svg)

This repository contains microcontroller firmware for a USB device that can set the speed of an attached fan. It does this by using the fan's PWM (Pulse Width Modulation) input, and can also read back its current rotational speed from its tachometer output. It is designed to work with standard PC case or CPU fans.

It also contains some software for using such a device.

## Rationale

This project came about because I had need of a PC cooling fan that could be controlled based on system-reported temperatures, but don't have a motherboard with spare fan headers. There are a few commercial products that can do this, but they are all targeted at high-end PC cooling solutions with multiple fan and RGB LED outputs, and are thus much larger and more expensive than what I was looking for.

Most microcontrollers have hardware PWM outputs these days, so it's not particularly difficult to drive a PC fan and hook it up to a USB device for cheap. I figured someone must have already done this, but if so, I couldn't find it. There are plenty of "PWM fan controller" projects out there, but most of those integrate the temperature feedback loop so they can run without being connected to a PC. In my case, the PC is what is providing the temperature data, so it needs to be the controller. Thus was born a "controllable PWM fan" project.

## Firmware

The [firmware](firmware) directory has the source code for the microcontroller firmware. It uses the [AVR Arduino core](https://github.com/arduino/ArduinoCore-avr) and can be built using [PlatformIO](https://platformio.org/).

### Features

The firmware currently supports the following features:
* Set PWM output duty cycle (for fan speed) and period (for PWM frequency), both in units of 16MHz clock cycles
* Get fan rotational speed in RPM (revolutions per minute)
* Set LED state to on, off, blink, or alert mode; default is alert mode, which will blink if fan stall is detected, otherwise off
* Initiate device reboot, either normal or into bootloader, via configuration register
* All registers accessible via either USB control endpoint or via USB serial port
* On Windows OS (8.1 or later), auto-install device with the WinUSB driver on first plug

### Supported microcontroller hardware

The firmware currently targets the Atmel (Microchip) [ATmega32U4](https://www.microchip.com/en-us/product/ATmega32U4) AVR microcontroller, and should work without modification on any microcontroller board module that claims to be compatible with [Arduino Leonardo](https://docs.arduino.cc/hardware/leonardo) or (to be added soon) [Sparkfun Pro Micro](https://www.sparkfun.com/products/12640) development boards. Clones of these boards can be found for cheap at many online retailers. These boards have USB connectors on them so they can be connected to a PC easily and generally have a number of IO lines that can be wired up to external hardware.

Other ATmega32U4-based boards may work, too, although getting the LED output to work may require building from source instead of using the pre-built firmware files. Also, unless the board runs its microcontroller with 5V power supply, additional hardware components will be required to drive the fan's PWM input. The remainder of this document assumes the microcontroller is running with 5V.

### Supported fans

For the speed to be controllable, the fan must have a PWM input line. The standard PC fans with PWM input have 4-pin connectors for plugging into a matching motherboard header, and also include the tach output, which is needed to read back the rotational speed. It should also have 4 separate wires coming out of the fan into the connector. It it only has 2 wires, then that's probably a power supply connector, not a fan header connector.

If a fan has a 3-pin connector, it won't have the PWM input, but does have tach output. The firmware will still work with such a fan, but it will always run at full speed, and the only thing you'll be able to do with the firmware is read its rotational speed.

Standard PC fans are designed to run with 12V power supply, so usually cannot be run directly from power provided by USB. These would require either an extra power supply (such as a wall wart) or a boost converter to step up from 5V USB power to 12V.

An alternative would be to use a 5V fan. 5V fans that have PWM input are much less common, but they do exist. For example, Noctua makes a 120mm model [NF-F12 5V PWM](https://noctua.at/en/products/fan/nf-f12-5v-pwm), as well as a number of 5V PWM fans with other sizes and max speeds. With a 5V PWM fan, the only components that need to be added to the microcontroller board are a single pull-up resistor and the header for connecting the fan.

In all cases, if you are using USB power, make sure you do not exceed the maximum current of the USB port, usually 500mA. If using a boost converter to step up to 12V, this limit is on the 5V current, which will be significantly higher than the 12V current supplied to the fan.

### Connecting the fan to the microcontroller board

The firmware currently only supports a single fan connection.

Its PWM output is on pin PB5, which is normally labelled `D9` on microcontroller boards. This must be connected to the PWM input pin on the fan connector. This is the pin at the end of the connector outside the notches and fans usually have a blue wire going to this pin on the connector.

The tachometer input is on pin PD1, which is normally labelled `D2` or `SDA` on microcontroller boards. This must be connected to the tachometer (sometimes labelled as "sense") output on the fan connector. This is the next pin down from the PWM input and fans usually have a green wire going to this pin on the connector, but it could also be yellow if the wire for power is red. You must also connect a 10K resistor between this pin and `+5V` (sometimes labelled `Vcc`). Without this pull-up resistor, the firmware will not be able to read the rotational speed.

Power and ground lines must also be connected to the fan:

If you are using USB (5V) to power the fan, this will be usually be labelled `+5V` or `Vcc` on microcontroller boards. If you are using 12V to power the fan, this will need to connect to your additional power supply or the output of a boost converter. Connect this to the power pin on the fan connector, which is the next pin down from the tachometer output pin and fans usually have a yellow or red wire going to this pin.

Finally, connect `GND` (Ground) from your microcontroller board to the ground pin on the fan connector. This is is the pin on the opposite end of the connector from the PWM input, will be inside the notches, and fans almost always have a black wire going to this pin on the connector.

**Be very careful** not to connect the wires wrong. PC motherboard fan headers are keyed to the notches on the connector in order to prevent plugging the fan in backwards or off center. If you are using a bare 4-pin header to connect the fan you won't have that protection. Connecting the fan wrong can easily fry the fan, and if using 12V can also fry your microcontroller board or even the USB port on your PC. If in doubt, do a web search for "4-pin fan header pinout" and look for pictures that show how the fan notches line up with the wires for PWM, tach, power, and ground.

### Uploading the firmware

Pre-built firmware files can be found in the [Releases](https://github.com/sparky8512/usb-pwm-fan/releases) section of this repository. You'll need to pull out the `.hex` file that is appropriate for your development board. There are currently files for 3 different board types: `beetle`, `leonardo`, and `promicro16`. If your board has "Pro Micro" printed on it, it's probably a Sparkfun Pro Micro clone; otherwise, it's probably closer to Leonardo. The Beetle firmware is the same as the Leonardo firmware except it uses the [DFRobot Beetle](https://www.dfrobot.com/product-1075.html) VID/PID in its USB descriptors. I'm pretty sure the only significant difference is the configuration of the LED pins. Only 16MHz board firmwares are currently being built.

Once you have a firmware file to upload, you can use the `atmega32u4_upload.py` tool to upload it if your board is not already running firmware from this project. If your board is already running firmware from this project, you can use either that tool or the `upload` command of the `usb_fan_config.py` tool. See details for those tools below.

## Tools

The [util](util) directory has some [Python](https://www.python.org/) scripts that can be used to interact with USB devices running this project's firmware.

### Installation

 To install their prerequisites, in that directory, you can run:
```shell script
python -m pip -r requirements.txt
```
This should work on most platforms, but if you have a more exotic setup, you may need to skip the `libusb-package` package and install [`pyusb`](https://github.com/pyusb/pyusb) by hand, including whatever backend is appropriate for your system.

To run as non-root user on Linux, you will probably also have to open up device permissions, see the [pyusb FAQ](https://github.com/pyusb/pyusb/blob/master/docs/faq.rst#how-to-practically-deal-with-permission-issues-on-linux) for more info.

### usb_fan_config.py

`usb_fan_config.py` can perform most operations that are available in the USB device firmware, including setting fan speed, getting tachometer reading, and various configuration settings. For usage details, you can run:
```shell script
python usb_fan_config.py --help
```

### atmega32u4_upload.py

`atmega32u4_upload.py` can be used to upload firmware to an ATmega32U4-based development board, assuming it uses the Caterina bootloader, which most Arduino-focussed development boards do. This script is mostly just a wrapper around [AVRDUDE](https://github.com/avrdudes/avrdude), so you will need to install that somewhere and if it's not in PATH, let the script know where you put it.

For full usage details, you can run:
```shell script
python atmega32u4_upload.py --help
```

There are 4 main operating modes for this script:
1) If you already have firmware from this project running on your development board, you can invoke this script by running `usb_fan_config.py` with the `upload` command. This will avoid the need to specify which serial port the USB device is on.
2) If you have some other Arduino firmware installed, you can run this script directly and use the `--port` option to specify which serial port the device shows up as. Alternatively, you can use the `--serial-number` option to have the script identify which serial port to use by the USB device serial number.
3) If option 2 doesn't work, maybe because it's running some non-Arduino firmware or the firmware has disabled the USB serial port, you will have to manually reboot into the bootloader, which can be done by driving the reset line on the board (normally labelled `RST`) low (connect to `GND`) briefly. Some boards have a button that you can press for this. In any event, you should do this _after_ you have started `atmega32u4_upload.py` with the `--manual-reboot` option.
4) If the bootloader serial port auto-detect logic is not working for some reason, or you just don't want to wait for the script to start before initiating manual reboot, you can use the `--bootloader-port` option to specify which serial port the bootloader is using. In this mode, the bootloader must already be running before you start the script.

If your development board uses a different bootloader than Caterina, you will need to use an upload tool specific to that bootloader.

## FanControl plugin

The [plugin](plugin) directory has the source code for a plugin to Rémi Mercier's [Fan Control](https://getfancontrol.com/) program that will allow it to access fans connected to USB devices running this project's firmware. Note that this is a Windows-only application.

### Installation

Binary releases of the plugin can be found in the [Releases](https://github.com/sparky8512/usb-pwm-fan/releases) section of this repository.

To install the plugin, place the file `FanControl.UsbFanPlugin.dll` into the `Plugins` directory of your FanControl installation. If it doesn't detect your USB device, there may be useful messages in Fan Control log file, which is located in the FanControl installation directory.

## Project TODO list

Things that may happen at some point of the future:
* Better documentation... *much* better documentation
* ~~Python script for configuration and status~~
* ~~Python script for firmware upload~~
* Workflow actions for builds
* Firmware features
  * Extend for multiple fans
  * Save default configuration to EEPROM, restore on boot
  * Allow software configuration of which GPIO to use for LED output
  * Allow change serial number via software configuration
  * Allow disable serial port interface via software configuration
  * Add read of microcontroller temperature and voltage
* FanControl plugin features
  * Handle hot unplug/replug better
