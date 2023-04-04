using FanControl.UsbFan.WinApi;
using FanControl.Plugins;
using System;
using System.ComponentModel;

namespace FanControl.UsbFan
{
    internal class UsbFanControl : IPluginControlSensor, IDisposable
    {
        private readonly UsbDevice _dev;
        private readonly IPluginLogger _logger;
        private int _maxDuty;

        public string Id { get; }

        public string Name { get; }

        public float? Value { get; private set; }

        public UsbFanControl(UsbDevice dev, IPluginLogger _logger, string serialNumber)
        {
            _dev = dev;
            this._logger = _logger;
            Id = "UsbFan/Control/" + serialNumber;
            Name = "USB Fan " + serialNumber;
        }

        public void Dispose()
        {
            _dev.Dispose();
        }

        public void Update()
        {
            // Nothing to do
        }

        public void Set(float val)
        {
            ushort duty = (ushort)(val * _maxDuty / 100.0F);
            try
            {
                _dev.ControlWriteIntertface(0x10, duty, null);
            }
            catch (Win32Exception e)
            {
                int code = e.NativeErrorCode;
                if (code == Win32.ERROR_BAD_COMMAND)
                {
                    _logger.Log($"{Name}: unplug detected");
                }
                else
                {
                    _logger.Log($"Error setting {Name}: {e.Message} ({code})");
                }
            }
        }

        public void Reset()
        {
            try
            {
                _dev.ControlWriteIntertface(0xf0, 1, null);
            }
            catch (Win32Exception)
            {
                // Let Set deal with the error
                Set(0.0F);
            }
        }

        internal bool Initialize()
        {
            byte[] buf;
            try
            {
                buf = _dev.ControlReadInterface(0x11, 0, 2);
            }
            catch (Win32Exception e)
            {
                _logger.Log($"Error initialing control for {Name}: {e.Message} ({e.NativeErrorCode})");
                return false;
            }
            if (buf.Length >= 2)
            {
                _maxDuty = (buf[1] << 8) + buf[0];
                return true;
            }
            return false;
        }
    }
}
