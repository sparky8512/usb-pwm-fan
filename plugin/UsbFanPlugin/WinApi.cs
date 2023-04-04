using Microsoft.Win32.SafeHandles;
using System;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace FanControl.UsbFan.WinApi
{
    internal class Win32
    {
        internal const int ERROR_BAD_COMMAND = 0x16;
        internal const int ERROR_INSUFFICIENT_BUFFER = 0x7a;
        internal const int ERROR_NO_MORE_ITEMS = 0x103;

        internal static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);
    }

    internal class File
    {
        internal const uint GENERIC_READ = 0x80000000;
        internal const uint GENERIC_WRITE = 0x40000000;
        internal const uint FILE_SHARE_READ = 0x1;
        internal const uint FILE_SHARE_WRITE = 0x2;
        internal const uint OPEN_EXISTING = 3;
        internal const uint FILE_ATTRIBUTE_NORMAL = 0x80;
        internal const uint FILE_FLAG_OVERLAPPED = 0x40000000;

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        internal static extern SafeFileHandle CreateFile(String lpFileName, uint dwDesiredAccess, uint dwShareMode, IntPtr lpSecurityAttributes, uint dwCreationDisposition, uint dwFlagsAndAttributes, IntPtr hTemplateFile);
    }

    internal class Setup
    {
        internal const uint DIGCF_PRESENT = 0x02;
        internal const uint DIGCF_DEVICEINTERFACE = 0x10;

        [StructLayout(LayoutKind.Sequential)]
        internal struct SP_DEVICE_INTERFACE_DATA
        {
            internal uint cbSize;
            internal Guid InterfaceClassGuid;
            internal uint Flags;
            internal IntPtr Reserved;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        internal unsafe struct SP_DEVICE_INTERFACE_DETAIL_DATA
        {
            internal uint cbSize;
            internal fixed char DevicePath[1];
        }

        [DllImport("setupapi.dll", SetLastError = true)]
        internal static extern IntPtr SetupDiCreateDeviceInfoList(in Guid ClassGuid, IntPtr hwndParent);

        [DllImport("setupapi.dll", SetLastError = true)]
        internal static extern Int32 SetupDiDestroyDeviceInfoList(IntPtr DeviceInfoSet);

        [DllImport("setupapi.dll", SetLastError = true)]
        internal static extern bool SetupDiEnumDeviceInterfaces(IntPtr DeviceInfoSet, IntPtr DeviceInfoData, in Guid InterfaceClassGuid, uint MemberIndex, ref SP_DEVICE_INTERFACE_DATA DeviceInterfaceData);

        [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
        internal static extern IntPtr SetupDiGetClassDevsEx(in Guid ClassGuid, IntPtr Enumerator, IntPtr hwndParent, uint Flags, IntPtr DeviceInfoSet, IntPtr MachineName, IntPtr Reserved);

        [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
        internal static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr DeviceInfoSet, in SP_DEVICE_INTERFACE_DATA DeviceInterfaceData, IntPtr DeviceInterfaceDetailData, uint DeviceInterfaceDetailDataSize, out uint RequiredSize, IntPtr DeviceInfoData);
        [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
        internal static unsafe extern bool SetupDiGetDeviceInterfaceDetail(IntPtr DeviceInfoSet, in SP_DEVICE_INTERFACE_DATA DeviceInterfaceData, SP_DEVICE_INTERFACE_DETAIL_DATA* DeviceInterfaceDetailData, uint DeviceInterfaceDetailDataSize, IntPtr RequiredSize, IntPtr DeviceInfoData);
    }

    internal class WinUsb
    {
        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        internal struct WINUSB_SETUP_PACKET
        {
            internal byte RequestType;
            internal byte Request;
            internal ushort Value;
            internal ushort Index;
            internal ushort Length;
        }

        [DllImport("winusb.dll", SetLastError = true)]
        internal static extern bool WinUsb_ControlTransfer(IntPtr InterfaceHandle, WINUSB_SETUP_PACKET SetupPacket, byte[] Buffer, uint BufferLength, out uint LengthTransferred, IntPtr Overlapped);

        [DllImport("winusb.dll", SetLastError = true)]
        internal static extern bool WinUsb_GetDescriptor(IntPtr InterfaceHandle, byte DescriptorType, byte Index, ushort LanguageID, [Out] byte[] Buffer, uint BufferLength, out uint LengthTransferred);

        [DllImport("winusb.dll", SetLastError = true)]
        internal static extern bool WinUsb_Free(IntPtr InterfaceHandle);

        [DllImport("winusb.dll", SetLastError = true)]
        internal static extern bool WinUsb_Initialize(SafeFileHandle DeviceHandle, out IntPtr InterfaceHandle);
    }
}
