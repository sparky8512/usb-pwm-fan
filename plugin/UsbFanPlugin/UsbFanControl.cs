using FanControl.UsbFan.WinApi;
using FanControl.Plugins;
using System;
using System.ComponentModel;

namespace FanControl.UsbFan
{
    internal class UsbFanControl : IPluginControlSensor, IDisposable
    {
        private readonly HotplugWrapper _dev;
        private readonly IPluginLogger _logger;
        private int _maxDuty;

        public string Id { get; }

        public string Name { get; }

        public float? Value { get; private set; }

        public UsbFanControl(HotplugWrapper dev, IPluginLogger _logger, string serialNumber)
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
            catch (UnpluggedException) { }
            catch (Win32Exception e)
            {
                _logger.Log($"Error setting {Name}: {e.Message} ({e.NativeErrorCode})");
            }
        }

        public void Reset()
        {
            try
            {
                _dev.ControlWriteIntertface(0xf0, 1, null);
            }
            catch (UnpluggedException) { }
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
            catch (UnpluggedException) {
                // This should be exceedingly rare, so no point in taking
                // extraordinary measures to hadle it any better than if it
                // were unplugged just prior to init, instead of during init.
                _logger.Log($"{Name} unplugged during init, ignoring this device");
                return false;
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
