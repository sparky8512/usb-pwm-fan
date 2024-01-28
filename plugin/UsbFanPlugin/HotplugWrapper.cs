using FanControl.Plugins;
using FanControl.UsbFan.WinApi;
using System;
using System.ComponentModel;

namespace FanControl.UsbFan
{
    /// <summary>
    /// Indicates failure due to device currently being unplugged
    /// </summary>
    public class UnpluggedException : Exception
    {
        public UnpluggedException() { }
    }

    /// <summary>
    /// A wrapper around <see cref="UsbDevice">UsbDevice</see> objects that
    /// manages rescanning for device being replugged when it is unplugged.
    /// </summary>
    public class HotplugWrapper
    {
        private UsbDevice _device;
        private readonly IPluginLogger _logger;
        private readonly Guid _guid;
        private readonly string _serialNumber;

        public HotplugWrapper(UsbDevice device, Plugins.IPluginLogger logger, in Guid guid, string serialNumber)
        {
            _device = device;
            _logger = logger;
            _guid = guid;
            _serialNumber = serialNumber;
        }

        public void Dispose()
        {
            if (_device != null)
            {
                _device.Dispose();
                _device = null;
            }
        }

        private void Unplug()
        {
            _logger.Log($"{_serialNumber}: unplug detected");
            _device.Dispose();
            _device = null;
        }

        private void Replug()
        {
            if (_device != null)
            {
                return;
            }

            UsbDevice.EnumerateDevices(in _guid, (UsbDevice usbDevice) =>
            {
                try
                {
                    if (_device != null || usbDevice.GetSerialNumber() != _serialNumber)
                    {
                        return false;
                    }

                    _device = usbDevice;
                    _logger.Log($"{_serialNumber}: replug detected");
                    return true;
                }
                catch (Win32Exception)
                {
                    // This can happen if, for example, the device is unplugged in the middle
                    return false;
                }
            });

            if (_device == null)
            {
                throw new UnpluggedException();
            }
        }

        /// <remarks>
        /// See <see cref="UsbDevice.ControlReadDevice(byte, ushort, ushort, ushort, bool)">UsbDevice.ControlReadDevice</see>
        /// for description and param detail.
        /// </remarks>
        /// <exception cref="UnpluggedException">Device is currently unplugged</exception>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public byte[] ControlReadDevice(byte request, ushort value, ushort index, ushort length, bool isVendor = true)
        {
            Replug();
            try
            {
                return _device.ControlReadDevice(request, value, index, length, isVendor);
            }
            catch (Win32Exception e) when (e.NativeErrorCode == Win32.ERROR_BAD_COMMAND)
            {
                Unplug();
                // Try again, in case it has already been replugged.
                return ControlReadDevice(request, value, index, length, isVendor);
            }
        }

        /// <remarks>
        /// See <see cref="UsbDevice.ControlReadInterface(byte, ushort, ushort, bool)">UsbDevice.ControlReadInterface</see>
        /// for description and param detail.
        /// </remarks>
        /// <exception cref="UnpluggedException">Device is currently unplugged</exception>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public byte[] ControlReadInterface(byte request, ushort value, ushort length, bool isVendor = true)
        {
            Replug();
            try
            {
                return _device.ControlReadInterface(request, value, length, isVendor);
            }
            catch (Win32Exception e) when (e.NativeErrorCode == Win32.ERROR_BAD_COMMAND)
            {
                Unplug();
                // Try again, in case it has already been replugged.
                return ControlReadInterface(request, value, length, isVendor);
            }
        }

        /// <remarks>
        /// See <see cref="UsbDevice.ControlWriteDevice(byte, ushort, ushort, byte[], bool)">UsbDevice.ControlWriteDevice</see>
        /// for description and param detail.
        /// </remarks>
        /// <exception cref="UnpluggedException">Device is currently unplugged</exception>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public uint ControlWriteDevice(byte request, ushort value, ushort index, byte[] data = null, bool isVendor = true)
        {
            Replug();
            try
            {
                return _device.ControlWriteDevice(request, value, index, data, isVendor);
            }
            catch (Win32Exception e) when (e.NativeErrorCode == Win32.ERROR_BAD_COMMAND)
            {
                Unplug();
                // Try again, in case it has already been replugged.
                return ControlWriteDevice(request, value, index, data, isVendor);
            }
        }

        /// <remarks>
        /// See <see cref="UsbDevice.ControlWriteIntertface(byte, ushort, byte[], bool)">UsbDevice.ControlWriteIntertface</see>
        /// for description and param detail.
        /// </remarks>
        /// <exception cref="UnpluggedException">Device is currently unplugged</exception>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public uint ControlWriteIntertface(byte request, ushort value, byte[] data = null, bool isVendor = true)
        {
            Replug();
            try
            {
                return _device.ControlWriteIntertface(request, value, data, isVendor);
            }
            catch (Win32Exception e) when (e.NativeErrorCode == Win32.ERROR_BAD_COMMAND)
            {
                Unplug();
                // Try again, in case it has already been replugged.
                return ControlWriteIntertface(request, value, data, isVendor);
            }
        }
    }
}
