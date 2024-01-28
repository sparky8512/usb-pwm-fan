using FanControl.UsbFan.WinApi;
using FanControl.Plugins;
using System;
using System.ComponentModel;

namespace FanControl.UsbFan
{
    internal class UsbFanSensor : IPluginSensor, IDisposable
    {
        private readonly HotplugWrapper _dev;
        private readonly IPluginLogger _logger;

        public string Id { get; }

        public string Name { get; }

        public float? Value { get; private set; }

        public UsbFanSensor(HotplugWrapper dev, IPluginLogger _logger, string serialNumber)
        {
            _dev = dev;
            this._logger = _logger;
            Id = "UsbFan/Sensor/" + serialNumber;
            Name = "USB Fan " + serialNumber;
        }

        public void Dispose()
        {
            _dev.Dispose();
        }

        public void Update()
        {
            try
            {
                byte[] buf = _dev.ControlReadInterface(0x12, 0, 2);
                if (buf.Length >= 2)
                {
                    Value = (buf[1] << 8) + buf[0];
                }
            }
            catch (UnpluggedException) {
                Value = float.NaN;
            }
            catch (Win32Exception e) {
                _logger.Log($"Error updating {Name}: {e.Message} ({e.NativeErrorCode})");
            }
        }
    }
}
