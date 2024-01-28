//
// Sketch entry point
//

#include <Arduino.h>

#include "UsbPwmDevice.h"

#include "USBCore.h"

#include <avr/sleep.h>
#include <avr/wdt.h>

// Define to wait ~5 seconds at start for USB serial to connect
//#define SERIAL_CONNECT_WAIT

// Define to engage the bootloader on unexpected watchdog reboot; this is a
// failsafe for development and should not be needed in released firmware
//#define BOOTLOAD_ON_WATCHDOG

// Work around missing general purpose LED output on Micro Pro, use the "TX"
// LED instead. This will fight with the USB core code over the state of that
// LED, but this is the best we can do without replacing the pins_arduino.h
// file for that board.
#ifdef ALT_LED_BUILTIN
#undef LED_BUILTIN
#define LED_BUILTIN ALT_LED_BUILTIN
#endif

// And of course that LED has to be inverted, too...
#ifdef LED_INVERTED
#define LED_ON LOW
#define LED_OFF HIGH
#else
#define LED_ON HIGH
#define LED_OFF LOW
#endif

#define STATE_IDLE 0
#define STATE_READ_REGISTER 1
#define STATE_WRITE_REGISTER 2
#define STATE_WRITE_VALUE 3
#define STATE_ERROR 4
static int command_state = STATE_IDLE;
static int command_register;
static long command_value;
static bool command_hex_mode;

static int command_buffer_length;
static uint8_t command_buffer[20];

static int sendToBuffer(uint8_t flags, const void* data, int length)
{
    if (length > (int)sizeof(command_buffer)) {
        length = sizeof(command_buffer);
    }

    if (flags & TRANSFER_PGM) {
        memcpy_P(command_buffer, data, length);
    } else {
        memcpy(command_buffer, data, length);
    }
    command_buffer_length = length;

    return length;
}

static void serialChar(char c)
{
    if (c == '\n' || c == '\r') {
        Serial.println();
        if (command_state == STATE_READ_REGISTER && command_register >= 0) {
            cli();
            bool rv = TheUsbPwmDevice.readRegister(command_register, sendToBuffer);
            sei();
            if (rv) {
                if (command_register == 0xf8) {
                    for (uint8_t i = 0; i < command_buffer_length; i++) {
                        Serial.write(command_buffer[i]);
                    }
                    Serial.println();
                } else {
                    Serial.println(*(uint16_t*)command_buffer);
                }
            } else {
                Serial.println(F("READ ERROR"));
            }
        } else if (command_state == STATE_WRITE_VALUE && command_value >= 0) {
            cli();
            bool rv = TheUsbPwmDevice.writeRegister(command_register, command_value);
            sei();
            if (!rv) {
                Serial.println(F("WRITE ERROR"));
            }
        } else if (command_state != STATE_IDLE) {
            Serial.println(F("ERROR"));
        }

        command_state = STATE_IDLE;
        return;
    }

    // Don't echo back control or non-ASCII chars
    if (c < 0x20 || c >= 127) {
        c = '~';
        command_state = STATE_ERROR;
    }

    Serial.write(c);
    if (command_state == STATE_IDLE) {
        if (c == 'R') {
            command_state = STATE_READ_REGISTER;
        } else if (c == 'W') {
            command_state = STATE_WRITE_REGISTER;
        } else {
            command_state = STATE_ERROR;
        }
        command_register = -1;
        command_value = -1;
        command_hex_mode = false;
    } else if (command_state == STATE_READ_REGISTER || 
               command_state == STATE_WRITE_REGISTER ||
               command_state == STATE_WRITE_VALUE) {
        // Convert to upper case
        c |= 0x20;

        long digits = command_state == STATE_WRITE_VALUE ? command_value : command_register;

        if (digits < 0 && c != 'x') {
            // Ignore leading space
            if (c == ' ') {
                return;
            }
            digits = 0;
        } else if (digits == 0 && c != 'x' && c != ',' && !command_hex_mode) {
            // Disallow leading 0, other than hex prefix
            command_state = STATE_ERROR;
            return;
        }

        if (c >= '0' && c <= '9') {
            digits = digits * (command_hex_mode ? 16 : 10) + c - '0';
        } else if (c >= 'a' && c <= 'f' && command_hex_mode) {
            digits = digits * 16 + c - 'a' + 10;
        } else if (c == 'x' && digits == 0 && !command_hex_mode) {
            digits = -1;
            command_hex_mode = true;
        } else if (command_state == STATE_WRITE_REGISTER && c == ',') {
            command_register = digits;
            if (command_register > 0xff) {
                command_state = STATE_ERROR;
            } else {
                command_hex_mode = false;
                command_state = STATE_WRITE_VALUE;
            }
            return;
        } else {
            command_state = STATE_ERROR;
        }

        if (command_state == STATE_WRITE_VALUE) {
            command_value = digits;
            if (command_value > 0xffff) {
                command_state = STATE_ERROR;
            }
        } else {
            command_register = (int)digits;
            if (command_register > 0xff) {
                command_state = STATE_ERROR;
            }
        }
    }
}

void setup()
{
#ifdef BOOTLOAD_ON_WATCHDOG
    *(volatile uint16_t *)(RAMEND-1) = MAGIC_KEY;
    *(volatile uint16_t *)MAGIC_KEY_POS = MAGIC_KEY;
#endif
    wdt_enable(WDTO_2S);

    PORTB = 0;

    pinMode(LED_BUILTIN, OUTPUT);
    pinMode(9, OUTPUT);
    pinMode(2, INPUT);

    // Power off unneeded hardware units
    ADCSRA = 0;
    ACSR = 0b10000000;
    PRR0 = 0b10000101;
    PRR1 = 0b00011001;
    DIDR1 = 0b00000001;
    DIDR0 = 0b11110011;
    DIDR2 = 0b00011111;

    Serial.begin(115200);

#ifdef SERIAL_CONNECT_WAIT
    int wait_count = 0;
    while (!Serial && wait_count++ < 50) {
        delay(100);
        if ((WDTCSR & 0b00100111) != WDTO_120MS) {
            wdt_enable(WDTO_2S);
        }
    }
    Serial.println(F("PWM Fan start"));
#endif

    TheUsbPwmDevice.begin();
}

static bool blink_state;
static unsigned long next_blink;
static unsigned long stall_time;

void loop()
{
    unsigned long now = millis();
    uint8_t mode = TheUsbPwmDevice.getLedMode();
    if (mode == LED_MODE_AUTO) {
        bool stalled = TheUsbPwmDevice.checkStall();
        if (stalled) {
            if (stall_time == 0) {
                stall_time = now;
            }
            // Allow 1 sec for tachometer start up
            stalled = (now - stall_time > 1000);
        }
        if (stalled) {
            mode = LED_MODE_BLINK;
        } else {
            mode = LED_MODE_OFF;
        }
    }
    if (mode == LED_MODE_ON) {
        digitalWrite(LED_BUILTIN, LED_ON);
    } else if (mode == LED_MODE_OFF) {
        digitalWrite(LED_BUILTIN, LED_OFF);
    } else if (mode == LED_MODE_BLINK) {
        if (now > next_blink) {
            if (blink_state) {
                digitalWrite(LED_BUILTIN, LED_OFF);
                next_blink += 140;
            } else {
                digitalWrite(LED_BUILTIN, LED_ON);
                next_blink += 10;
            }
            blink_state = !blink_state;
        }
    }

    while (Serial.available()) {
        serialChar((char)Serial.read());
    }

    // WDTO_120MS is what the CDC driver uses to initiate reboot, so don't
    // interfere with that.
    if ((WDTCSR & 0b00100111) != WDTO_120MS) {
        // Note that wdt.h implies wdt_reset() is the right way to inform
        // watchdog things are OK, but that just seems to disable it?
        wdt_enable(WDTO_2S);
    }

    // Idle the CPU until next interrupt
    sleep_mode();
}
