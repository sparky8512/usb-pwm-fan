using FanControl.Plugins;
using FanControl.UsbFan.WinApi;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Text;

namespace FanControl.UsbFan
{
    public class UsbFanPlugin: IPlugin
    {
        private static readonly Guid FanInterfaceGuid = new Guid(0x1ad9f93b, 0x494c, 0x4dda, 0xa1, 0xe5, 0x2e, 0x2b, 0xab, 0x18, 0x10, 0x52);
        private const byte DeviceVersionMajor = 0;
        private const byte DeviceVersionMinor = 1;

        private readonly IPluginLogger _logger;
        private readonly IPluginDialog _dialog;
        private readonly List<UsbFanControl> _controls = new List<UsbFanControl>();
        private readonly List<UsbFanSensor> _sensors = new List<UsbFanSensor>();

        public UsbFanPlugin(IPluginLogger logger, IPluginDialog dialog)
        {
            _logger = logger;
            _dialog = dialog;
        }

        public string Name => "USB Fan";

        public void Close()
        {
            foreach (UsbFanControl control in _controls)
            {
                control.Dispose();
            }
            foreach (UsbFanSensor sensor in _sensors)
            {
                sensor.Dispose();
            }
            _controls.Clear();
            _sensors.Clear();
        }

        private bool CheckVersion(UsbDevice device)
        {
            byte[] buf = device.ControlReadInterface(0x00, 0, 2);
            if (buf.Length < 2)
            {
                return false;
            }
            // For pre-release, insist on exact minor version match
            if (buf[1] != DeviceVersionMajor || buf[0] != DeviceVersionMinor)
            {
                _logger.Log($"Found USB fan device, but incompatible firware revision: {buf[1]}, {buf[0]}");
                return false;
            }

            return true;
        }

        public void Initialize()
        {
            UsbDevice.EnumerateDevices(in FanInterfaceGuid, (UsbDevice device) =>
            {
                try
                {
                    string serialNumber = device.GetSerialNumber();
                    if (serialNumber == null) {
                        _logger.Log($"Error getting serial number from USB fan device {device.Name}");
                        return false;
                    }

                    bool rv = CheckVersion(device);
                    if (!rv) {
                        _logger.Log($"Error checking version for USB fan device {serialNumber}");
                        return false;
                    }

                    UsbFanControl control = new UsbFanControl(device, _logger, serialNumber);
                    if (control.Initialize())
                    {
                        _controls.Add(control);
                    }
                    _sensors.Add(new UsbFanSensor(device, _logger, serialNumber));

                    return true;
                }
                catch (Win32Exception e)
                {
                    // This can happen if, for example, the device is unplugged in the middle
                    _logger.Log($"Error enumerating USB fan device {device.Name}: {e.Message} ({e.NativeErrorCode})");
                    return false;
                }
            });
        }

        public void Load(IPluginSensorsContainer _container)
        {
            _container.ControlSensors.AddRange(_controls);
            _container.FanSensors.AddRange(_sensors);
        }
    }
}
