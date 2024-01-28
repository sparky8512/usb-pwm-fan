#ifndef UsbPwmDevice_h
#define UsbPwmDevice_h

#include "PluggableUSB.h"
#include "USBCore.h"

#define LED_MODE_AUTO 0
#define LED_MODE_ON 1
#define LED_MODE_OFF 2
#define LED_MODE_BLINK 3
#define LED_MODE_MAX LED_MODE_BLINK

class UsbPwmDevice : public PluggableUSBModule
{
public:
    UsbPwmDevice(void);
    int begin(void);
    bool readRegister(uint8_t reg, int(*send)(uint8_t, const void*, int));
    bool writeRegister(uint8_t reg, uint16_t value);
    uint8_t getLedMode();
    bool checkStall();

protected:
    int getInterface(uint8_t* interfaceCount);
    int getDescriptor(USBSetup& setup);
    bool setup(USBSetup& setup);
    uint8_t getShortName(char* name);
};

extern UsbPwmDevice TheUsbPwmDevice;

#endif
