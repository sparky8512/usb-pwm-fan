using FanControl.UsbFan.WinApi;
using Microsoft.Win32.SafeHandles;
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace FanControl.UsbFan
{
    /// <summary>
    /// Represents a USB device that uses the WinUSB driver
    /// </summary>
    public class UsbDevice : IDisposable
    {
        private static readonly Guid WinusbClassGuid = new Guid(0x88bae032, 0x5a81, 0x49f0, 0xbc, 0x3d, 0xa4, 0xff, 0x13, 0x82, 0x16, 0xd6);

        private readonly SafeFileHandle _hFile;
        private IntPtr _hDev;

        public string Name { get; private set; }

        public UsbDevice(SafeFileHandle hFile, IntPtr hDev, string name)
        {
            _hFile = hFile;
            _hDev = hDev;
            this.Name = name;
        }

        public void Dispose()
        {
            if (_hDev != Win32.INVALID_HANDLE_VALUE)
            {
                WinUsb.WinUsb_Free(_hDev);
                _hFile.Close();
                _hDev = Win32.INVALID_HANDLE_VALUE;
            }
            GC.SuppressFinalize(this);
        }

        ~UsbDevice()
        {
            WinUsb.WinUsb_Free(_hDev);
        }

        /// <summary>
        /// Get specified USB descriptor from the device
        /// </summary>
        /// <param name="length">Maximum length, in bytes</param>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public byte[] GetDescriptor(byte type, byte index, uint length)
        {
            byte[] data = new byte[length];
            uint bytesTransferred;
            bool rv = WinUsb.WinUsb_GetDescriptor(_hDev, type, index, 0, data, length, out bytesTransferred);
            if (!rv) { throw new Win32Exception(); }

            if (bytesTransferred < length)
            {
                Array.Resize(ref data, (int)bytesTransferred);
            }
            return data;
        }

        /// <summary>
        /// Perform a read operation on control endpoint 0 directed to the device
        /// </summary>
        /// <remarks>
        /// See <see cref="ControlRead(byte, byte, ushort, ushort, ushort)">ControlRead</see> for
        /// more param detail.
        /// </remarks>
        /// <param name="isVendor">If true, use vendor type, else use standard type</param>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public byte[] ControlReadDevice(byte request, ushort value, ushort index, ushort length, bool isVendor = true)
        {
            byte type = (byte)(isVendor ? 0xC0 : 0x80);
            return ControlRead(type, request, value, index, length);
        }

        /// <summary>
        /// Perform a read operation on control endpoint 0 directed to the interface
        /// </summary>
        /// <remarks>
        /// Interface index used will be the one associated with the GUID used to open the device.
        /// See <see cref="ControlRead(byte, byte, ushort, ushort, ushort)">ControlRead</see> for
        /// more param detail.
        /// </remarks>
        /// <param name="isVendor">If true, use vendor type, else use standard type</param>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public byte[] ControlReadInterface(byte request, ushort value, ushort length, bool isVendor = true)
        {
            // index filled in by WinUSB
            byte type = (byte)(isVendor ? 0xC1 : 0x81);
            return ControlRead(type, request, value, 0, length);
        }

        /// <summary>
        /// Perform a read operation on control endpoint 0
        /// </summary>
        /// <param name="type">bmRequestType value to use in setup packet</param>
        /// <param name="request">bRequest value to use in setup packet</param>
        /// <param name="value">wValue value to use in setup packet</param>
        /// <param name="index">wIndex value to use in setup packet</param>
        /// <param name="length">Maximum length of data stage, in bytes, must be no larger than 4096</param>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public byte[] ControlRead(byte type, byte request, ushort value, ushort index, ushort length)
        {
            if (length > 4096)
            {
                throw new ArgumentException();
            }

            byte[] data = new byte[length];
            WinUsb.WINUSB_SETUP_PACKET setup;

            setup.RequestType = type;
            setup.Request = request;
            setup.Value = value;
            setup.Index = index;
            setup.Length = length;

            uint bytesTransferred;
            bool rv = WinUsb.WinUsb_ControlTransfer(_hDev, setup, data, length, out bytesTransferred, IntPtr.Zero);
            if (!rv) { throw new Win32Exception(); }

            if (bytesTransferred < length)
            {
                Array.Resize(ref data, (int)bytesTransferred);
            }
            return data;
        }

        /// <summary>
        /// Perform a write operation on control endpoint 0 directed to the device
        /// </summary>
        /// <remarks>
        /// See <see cref="ControlWrite(byte, byte, ushort, ushort, byte[])">ControlWrite</see> for
        /// more param detail.
        /// </remarks>
        /// <param name="isVendor">If true, use vendor type, else use standard type</param>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public uint ControlWriteDevice(byte request, ushort value, ushort index, byte[] data = null, bool isVendor = true)
        {
            // index filled in by WinUSB
            byte type = (byte)(isVendor ? 0x40 : 0x00);
            return ControlWrite(type, request, value, index, data);
        }

        /// <summary>
        /// Perform a write operation on control endpoint 0 directed to the interface
        /// </summary>
        /// <remarks>
        /// Interface index used will be the one associated with the GUID used to open the device.
        /// See <see cref="ControlWrite(byte, byte, ushort, ushort, byte[])">ControlWrite</see> for
        /// more param detail.
        /// </remarks>
        /// <param name="isVendor">If true, use vendor type, else use standard type</param>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public uint ControlWriteIntertface(byte request, ushort value, byte[] data = null, bool isVendor = true)
        {
            // index filled in by WinUSB
            byte type = (byte)(isVendor ? 0x41 : 0x01);
            return ControlWrite(type, request, value, 0, data);
        }

        /// <summary>
        /// Perform a write operation on control endpoint 0
        /// </summary>
        /// <param name="type">bmRequestType value to use in setup packet</param>
        /// <param name="request">bRequest value to use in setup packet</param>
        /// <param name="value">wValue value to use in setup packet</param>
        /// <param name="index">wIndex value to use in setup packet</param>
        /// <param name="data">Data to write in data stage, must be no larger than 4096 bytes</param>
        /// <exception cref="Win32Exception">Error reported by WinUSB</exception>
        public uint ControlWrite(byte type, byte request, ushort value, ushort index, byte[] data = null)
        {
            if (data == null)
            {
                // WinUsb_ControlTransfer docs do not mark Buffer arg as
                // optional, even if length is 0
                data = new byte[0];
            }

            ushort length = (ushort)data.Length;
            if (length > 4096)
            {
                throw new ArgumentException();
            }

            WinUsb.WINUSB_SETUP_PACKET setup;

            setup.RequestType = type;
            setup.Request = request;
            setup.Value = value;
            setup.Index = index;
            setup.Length = length;

            uint bytesTransferred;
            bool rv = WinUsb.WinUsb_ControlTransfer(_hDev, setup, data, length, out bytesTransferred, IntPtr.Zero);
            if (!rv) { throw new Win32Exception(); }

            return bytesTransferred;
        }

        public string GetSerialNumber()
        {
            // Get serial numbmer string index from device descriptor
            byte[] buf = GetDescriptor(1, 0, 18);
            if (buf.Length < 17 || buf[0] < 17)
            {
                return null;
            }
            byte iSerialNumber = buf[16];
            if (iSerialNumber == 0)
            {
                return null;
            }

            // Then the actual serial number
            buf = GetDescriptor(3, iSerialNumber, 1024);
            if (buf.Length < 2 || buf[0] < 2)
            {
                return null;
            }

            int length = (buf.Length < buf[0] ? buf.Length : buf[0]) - 2;
            return Encoding.Unicode.GetString(buf, 2, length);
        }

        /// <summary>
        /// The "unsafe" bits dealing with the variable length C struct SP_DEVICE_INTERFACE_DETAIL_DATA
        /// </summary>
        private unsafe static string GetDevicePath(IntPtr hDevInfo, in Setup.SP_DEVICE_INTERFACE_DATA ifaceData)
        {
            uint bufSize;
            bool rv = Setup.SetupDiGetDeviceInterfaceDetail(hDevInfo, in ifaceData, IntPtr.Zero, 0, out bufSize, IntPtr.Zero);
            if (!rv && Marshal.GetLastWin32Error() != Win32.ERROR_INSUFFICIENT_BUFFER) { return null; }

            Setup.SP_DEVICE_INTERFACE_DETAIL_DATA* ifaceDetail = (Setup.SP_DEVICE_INTERFACE_DETAIL_DATA*)Marshal.AllocHGlobal((int)bufSize);
            try
            {
                // Marshal.SizeOf doesn't seem to get the struct size right on 32-bit
                ifaceDetail->cbSize = (uint)((IntPtr.Size == 4) ? Marshal.SizeOf(typeof(uint)) + Marshal.SystemDefaultCharSize : Marshal.SizeOf(typeof(Setup.SP_DEVICE_INTERFACE_DETAIL_DATA)));
                rv = Setup.SetupDiGetDeviceInterfaceDetail(hDevInfo, in ifaceData, ifaceDetail, bufSize, IntPtr.Zero, IntPtr.Zero);
                if (rv)
                {
                    return Marshal.PtrToStringAuto((IntPtr)(ifaceDetail->DevicePath));
                }
                return null;
            }
            finally
            {
                Marshal.FreeHGlobal((IntPtr)ifaceDetail);
            }
        }

        /// <summary>
        /// Find all USB devices using the WinUSB driver that match a specific device interface GUID
        /// </summary>
        /// <remarks>
        /// Device interface GUIDs can be assigned to devices via .INF file when its driver is installed,
        /// or automatically using a properly formed Microsoft OS descriptor in the USB device.
        /// </remarks>
        /// <param name="guid">GUID to match against</param>
        /// <param name="callback">Function to call (synchronously) for each device found</param>
        public static void EnumerateDevices(in Guid guid, Func<UsbDevice, bool> callback)
        {
            IntPtr hDevInfo = Setup.SetupDiCreateDeviceInfoList(in WinusbClassGuid, IntPtr.Zero);
            if (hDevInfo == Win32.INVALID_HANDLE_VALUE)
            {
                return;
            }

            try
            {
                // On success, SetupDiGetClassDevsEx will return the same handle,
                // but in error case, still need to destroy it
                IntPtr hDevInfo2 = Setup.SetupDiGetClassDevsEx(in guid, IntPtr.Zero, IntPtr.Zero, Setup.DIGCF_PRESENT | Setup.DIGCF_DEVICEINTERFACE, hDevInfo, IntPtr.Zero, IntPtr.Zero);
                if (hDevInfo2 != Win32.INVALID_HANDLE_VALUE)
                {
                    uint index;
                    Setup.SP_DEVICE_INTERFACE_DATA ifaceData = new Setup.SP_DEVICE_INTERFACE_DATA();
                    for (index = 0; true; index++)
                    {
                        ifaceData.cbSize = (uint)Marshal.SizeOf(ifaceData);
                        bool rv = Setup.SetupDiEnumDeviceInterfaces(hDevInfo, IntPtr.Zero, in guid, index, ref ifaceData);
                        if (!rv) { break; }

                        string path = GetDevicePath(hDevInfo, in ifaceData);
                        if (path == null) { continue; }

                        SafeFileHandle hFile = File.CreateFile(path, File.GENERIC_READ | File.GENERIC_WRITE, File.FILE_SHARE_READ | File.FILE_SHARE_WRITE, IntPtr.Zero, File.OPEN_EXISTING, File.FILE_ATTRIBUTE_NORMAL | File.FILE_FLAG_OVERLAPPED, IntPtr.Zero);
                        if (!hFile.IsInvalid)
                        {
                            IntPtr hDev;
                            rv = WinUsb.WinUsb_Initialize(hFile, out hDev);
                            if (rv)
                            {
                                UsbDevice device = new UsbDevice(hFile, hDev, path);
                                rv = callback(device);
                                if (!rv)
                                {
                                    device.Dispose();
                                }
                            }
                            else
                            {
                                hFile.Close();
                            }
                        }
                    }
                }
            }
            finally
            {
                Setup.SetupDiDestroyDeviceInfoList(hDevInfo);
            }
        }
    }
}
