//
// USB-facing part of the PWM fan interface
//

#include <Arduino.h>

#include "UsbPwmDevice.h"

#include "PluggableUSB.h"
#include "USBCore.h"
#include "USBDesc.h"

#include <avr/boot.h>
#include <avr/sleep.h>
#include <avr/wdt.h>

#if ISERIAL_MAX_LEN >= 10 * 8/5
#define SERIAL_BYTES (10 * 8/5)
#else
#define SERIAL_BYTES ISERIAL_MAX_LEN
#endif

#define NUM_PULSE_TIMES 16

static uint8_t pending_tccr1a;

ISR(TIMER1_OVF_vect)
{
    TCCR1A = pending_tccr1a;
    TIMSK1 = 0;
}

static uint8_t pulse_index;
static unsigned long pulse_times[NUM_PULSE_TIMES];
static volatile unsigned long last_pulse;
static volatile unsigned long pulse_delta;

ISR(INT1_vect)
{
    uint8_t i = (pulse_index + 1) % NUM_PULSE_TIMES;
    pulse_index = i;
    unsigned long old_time = pulse_times[i];
    unsigned long new_time = micros();
    last_pulse = new_time;
    pulse_times[i] = new_time;
    pulse_delta = new_time - old_time;
}

UsbPwmDevice::UsbPwmDevice(void) : PluggableUSBModule(0, 1, NULL), ledMode(0)
{
    PluggableUSB().plug(this);
}

int UsbPwmDevice::getInterface(uint8_t* interfaceCount)
{
    *interfaceCount += 1;
    InterfaceDescriptor iface =
        D_INTERFACE(pluggedInterface, 0, USB_DEVICE_CLASS_VENDOR_SPECIFIC, 0xFD, 0xFF);
    return USB_SendControl(0, &iface, sizeof(iface));
}

#define VERSION_MAJOR 1
#define VERSION_MINOR 0
static const uint8_t version[2] PROGMEM = { VERSION_MINOR, VERSION_MAJOR };

//
// USB Binary Device Object Store (BOS) descriptor.
//
// This includes 2 platform device capability descriptors. One that points to
// the Microsoft OS descriptor below and one that uniquely identifies this
// device as having the PWM fan interface supported by this firmware.
//
// See USB 3.2 Specification, sections 9.6.2 and 9.6.2.4.
//
// Note that use of this descriptor is usually conditional on the device
// reporting its USB version as at least 2.1.
//
const uint8_t BOS_DESCRIPTOR[] PROGMEM = {
    0x05, 0x0f, 0x38, 0x00, 0x02, 0x1c, 0x10, 0x05,
    0x00, 0xdf, 0x60, 0xdd, 0xd8, 0x89, 0x45, 0xc7,
    0x4c, 0x9c, 0xd2, 0x65, 0x9d, 0x9e, 0x64, 0x8a,
    0x9f, 0x00, 0x00, 0x03, 0x06, 0xb2, 0x00, 0x02,
    0x00, 0x17, 0x10, 0x05, 0x00, 0x3b, 0xf9, 0xd9,
    0x1a, 0x4c, 0x49, 0xda, 0x4d, 0xa1, 0xe5, 0x2e,
    0x2b, 0xab, 0x18, 0x10, 0x52, VERSION_MINOR, VERSION_MAJOR, 0x02
};

//
// Magic Microsoft Goo (TM)
//
// Along with part of the BOS descriptor above, this allows Windows OS (8.1
// and later) to detect this device as needing the WinUSB driver installed,
// which it will do automatically when first plugged in.
//
// It also assigns a device interface GUID, which is necessary for user
// applications to be able to enumerate it.
//
// For detail, see the Microsoft OS 2.0 Descriptors Specification document.
//
const uint8_t MS_OS_20_DESCRIPTORS[] PROGMEM = {
    0x0a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x06,
    0xb2, 0x00, 0x08, 0x00, 0x01, 0x00, 0x00, 0x00,
    0xa8, 0x00, 0x08, 0x00, 0x02, 0x00, 0x02, 0x00,
    0xa0, 0x00, 0x14, 0x00, 0x03, 0x00, 0x57, 0x49,
    0x4e, 0x55, 0x53, 0x42, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x84, 0x00,
    0x04, 0x00, 0x07, 0x00, 0x2a, 0x00, 0x44, 0x00,
    0x65, 0x00, 0x76, 0x00, 0x69, 0x00, 0x63, 0x00,
    0x65, 0x00, 0x49, 0x00, 0x6e, 0x00, 0x74, 0x00,
    0x65, 0x00, 0x72, 0x00, 0x66, 0x00, 0x61, 0x00,
    0x63, 0x00, 0x65, 0x00, 0x47, 0x00, 0x55, 0x00,
    0x49, 0x00, 0x44, 0x00, 0x73, 0x00, 0x00, 0x00,
    0x50, 0x00, 0x7b, 0x00, 0x31, 0x00, 0x41, 0x00,
    0x44, 0x00, 0x39, 0x00, 0x46, 0x00, 0x39, 0x00,
    0x33, 0x00, 0x42, 0x00, 0x2d, 0x00, 0x34, 0x00,
    0x39, 0x00, 0x34, 0x00, 0x43, 0x00, 0x2d, 0x00,
    0x34, 0x00, 0x44, 0x00, 0x44, 0x00, 0x41, 0x00,
    0x2d, 0x00, 0x41, 0x00, 0x31, 0x00, 0x45, 0x00,
    0x35, 0x00, 0x2d, 0x00, 0x32, 0x00, 0x45, 0x00,
    0x32, 0x00, 0x42, 0x00, 0x41, 0x00, 0x42, 0x00,
    0x31, 0x00, 0x38, 0x00, 0x31, 0x00, 0x30, 0x00,
    0x35, 0x00, 0x32, 0x00, 0x7d, 0x00, 0x00, 0x00,
    0x00, 0x00
};

int UsbPwmDevice::getDescriptor(USBSetup& setup)
{
    if (setup.wValueH == 0x0F && setup.wValueL == 0 && setup.wIndex == 0) {
        return USB_SendControl(TRANSFER_PGM, &BOS_DESCRIPTOR, sizeof(BOS_DESCRIPTOR));
    }
    return 0;
}

bool UsbPwmDevice::readRegister(uint8_t reg, int(*send)(uint8_t, const void*, int))
{
    if (reg == 0x00) {
        return send(TRANSFER_PGM, &version, sizeof(version)) >= 0;
    } else if (reg == 0x10) {
        uint16_t pwm_duty;
        if (pending_tccr1a & 0b10000000) {
            pwm_duty = OCR1A + 1;
        } else {
            pwm_duty = 0;
        }
        return send(0, &pwm_duty, sizeof(pwm_duty)) >= 0;
    } else if (reg == 0x11) {
        uint16_t pwm_period = ICR1 + 1;
        return send(0, &pwm_period, sizeof(pwm_period)) >= 0;
    } else if (reg == 0x12) {
        // Interrupts are disabled, so can access these without worrying about
        // atomicity
        unsigned long delta = pulse_delta;
        unsigned long check_time = pulse_times[pulse_index];

        uint16_t rpm;
        if (delta == 0 || micros() - check_time > 1000000) {
            // No pulse in over a second, assume stalled
            rpm = 0;
        } else {
            // 2 pulses per revolution
            rpm = (unsigned long)60000000*(NUM_PULSE_TIMES/2)/delta;
        }
        return send(0, &rpm, sizeof(rpm)) >= 0;
    } else if (reg == 0xf1) {
        uint16_t mode = ledMode;
        return send(0, &mode, sizeof(mode)) >= 0;
    } else if (reg == 0xf8) {
        char buf[SERIAL_BYTES];
        getShortName(buf);
        return send(0, buf, SERIAL_BYTES) >= 0;
    }
    return false;
}

bool UsbPwmDevice::writeRegister(uint8_t reg, uint16_t value)
{
    if (reg == 0x10) {
        // Set PWM duty high time
        uint8_t new_tccr1a;
        if (value) {
            new_tccr1a = 0b10000010;    // COM1A[1:0] = 10, WGM1[1:0] = 10
            OCR1A = value - 1;
        } else {
            // Special case for value 0: turn PWM off
            new_tccr1a = 0b00000010;    // COM1A[1:0] = 00, WGM1[1:0] = 10
        }
        if (pending_tccr1a != new_tccr1a) {
            // TCCR1A is not double-buffered the way OCR1A is, so defer
            // update to the end of this PWM period.
            pending_tccr1a = new_tccr1a;
            TIFR1 = _BV(TOV1);
            TIMSK1 = _BV(TOIE1);
        }
        return true;
    } else if (reg == 0x11) {
        // Set PWM period time
        ICR1 = value - 1;
        TCNT1 = 0;
        return true;
    } else if (reg == 0xf0) {
        // Reboot control
        uint16_t key;
        if (value == 1) {
            // Reset configuration to default
            begin();
            return true;
        } else if (value == 2) {
            // Regular reboot
            key = 0x0000;
        } else if (value == 3) {
            // Reboot into bootloader
            key = MAGIC_KEY;
        } else if (value == 255) {
            // Watchdog test
        } else {
            // Silently ignore any other value
            return true;
        }

        cli();
        // Mimic what CDC_Setup does to invoke bootloader
        if (value != 255) {
            *(volatile uint16_t *)(RAMEND-1) = key;
            *(volatile uint16_t *)MAGIC_KEY_POS = key;
            wdt_enable(WDTO_15MS);
        }
        while (true) {
            sleep_mode();
        }
        // Never returns
    } else if (reg == 0xf1) {
        // LED control
        if (value <= LED_MODE_MAX) {
            ledMode = (uint8_t)value;
        }
        return true;
    }
    return false;
}

bool UsbPwmDevice::checkStall()
{
    bool stalled = false;
    uint8_t old_sreg = SREG;
    cli();
    if (pending_tccr1a & 0b10000000) {
        unsigned long check_time = pulse_times[pulse_index];
        if (pulse_delta == 0 || micros() - check_time > 1000000) {
            stalled = true;
        }
    }
    SREG = old_sreg;
    return stalled;
}

bool UsbPwmDevice::setup(USBSetup& setup)
{
    if (setup.bmRequestType == (REQUEST_DEVICETOHOST | REQUEST_VENDOR | REQUEST_DEVICE) &&
        setup.bRequest == 0x02 && setup.wIndex == 0x07) {
        return USB_SendControl(TRANSFER_PGM, &MS_OS_20_DESCRIPTORS, sizeof(MS_OS_20_DESCRIPTORS)) >= 0;
    } else if (setup.bmRequestType == (REQUEST_DEVICETOHOST | REQUEST_VENDOR | REQUEST_INTERFACE) &&
               setup.wIndex == pluggedInterface) {
        return readRegister(setup.bRequest, USB_SendControl);
    } else if (setup.bmRequestType == (REQUEST_HOSTTODEVICE | REQUEST_VENDOR | REQUEST_INTERFACE) &&
               setup.wIndex == pluggedInterface) {
        return writeRegister(setup.bRequest, ((uint16_t)setup.wValueH << 8) | setup.wValueL);
    }

    return false;
}

//
// This winds up as the serial number string descriptor and has a max length
// of ISERIAL_MAX_LEN chars. It must be an ASCII string.
//
uint8_t UsbPwmDevice::getShortName(char *name)
{
    uint16_t bits = 0;
    int have_bits = 0;
    int i = 0;
    for (uint8_t offset = 0; offset < SERIAL_BYTES; offset++) {
        if (have_bits < 5) {
            bits = bits | (boot_signature_byte_get(14 + i++) << have_bits);
            have_bits += 8;
        }
        uint8_t n = bits & 0x1f;
        name[offset] = n < 10 ? '0' + n : 'A' - 10 + n;
        bits = bits >> 5;
        have_bits -= 5;
    }
    return SERIAL_BYTES;
}

int UsbPwmDevice::begin(void)
{
    // Configure Timer 1 for 25KHz PWM, start with output off (0% duty cycle)
    TIMSK1 = 0;
    ICR1 = 639;
    OCR1A = 0;
    TCNT1 = 0;
    TCCR1A = pending_tccr1a = 0b00000010;    // COM1A[1:0] = 00, WGM1[1:0] = 10
    TCCR1B = 0b00011001;    // WGM1[3:2] = 11, CS1[2:0] = 001

    EIMSK = 0;
    EICRA = 0b00001100;
    EIFR = 0b00000010;
    EIMSK = 0b00000010;

    return 0;
}

UsbPwmDevice TheUsbPwmDevice;
