using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace VirtualCar.J2534.AbiProbe;

/// <summary>
/// ABI-only canary for Windows win-x86/win-x64 Native AOT.
/// DO NOT register this DLL as an adapter or use it for diagnostic tests.
/// All entry points explicitly fail closed; it never simulates any ECU.
/// </summary>
public static unsafe class J2534Exports
{
    private const uint ErrNotSupported = 0x00000001u;

    [UnmanagedCallersOnly(EntryPoint = "PassThruOpen", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruOpen(void* name, uint* device)
    {
        if (device != null) *device = 0;
        return ErrNotSupported;
    }

    [UnmanagedCallersOnly(EntryPoint = "PassThruClose", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruClose(uint device) => ErrNotSupported;

    [UnmanagedCallersOnly(EntryPoint = "PassThruConnect", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruConnect(uint device, uint protocol, uint flags, uint baud, uint* channel)
    {
        if (channel != null) *channel = 0;
        return ErrNotSupported;
    }

    [UnmanagedCallersOnly(EntryPoint = "PassThruDisconnect", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruDisconnect(uint channel) => ErrNotSupported;

    [UnmanagedCallersOnly(EntryPoint = "PassThruReadMsgs", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruReadMsgs(uint channel, void* messages, uint* count, uint timeout)
    {
        if (count != null) *count = 0;
        return ErrNotSupported;
    }

    [UnmanagedCallersOnly(EntryPoint = "PassThruWriteMsgs", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruWriteMsgs(uint channel, void* messages, uint* count, uint timeout)
    {
        if (count != null) *count = 0;
        return ErrNotSupported;
    }

    [UnmanagedCallersOnly(EntryPoint = "PassThruStartPeriodicMsg", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruStartPeriodicMsg(uint channel, void* message, uint* messageId, uint interval)
    {
        if (messageId != null) *messageId = 0;
        return ErrNotSupported;
    }

    [UnmanagedCallersOnly(EntryPoint = "PassThruStopPeriodicMsg", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruStopPeriodicMsg(uint channel, uint messageId) => ErrNotSupported;

    [UnmanagedCallersOnly(EntryPoint = "PassThruStartMsgFilter", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruStartMsgFilter(
        uint channel, uint filterType, void* mask, void* pattern, void* flowControl, uint* filterId)
    {
        if (filterId != null) *filterId = 0;
        return ErrNotSupported;
    }

    [UnmanagedCallersOnly(EntryPoint = "PassThruStopMsgFilter", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruStopMsgFilter(uint channel, uint filterId) => ErrNotSupported;

    [UnmanagedCallersOnly(EntryPoint = "PassThruSetProgrammingVoltage", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruSetProgrammingVoltage(uint device, uint pin, uint voltage)
        => ErrNotSupported;

    [UnmanagedCallersOnly(EntryPoint = "PassThruReadVersion", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruReadVersion(uint device, byte* firmware, byte* dll, byte* api)
        => ErrNotSupported;

    [UnmanagedCallersOnly(EntryPoint = "PassThruGetLastError", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruGetLastError(byte* description) => ErrNotSupported;

    [UnmanagedCallersOnly(EntryPoint = "PassThruIoctl", CallConvs = [typeof(CallConvStdcall)])]
    public static uint PassThruIoctl(uint channel, uint ioctl, void* input, void* output)
        => ErrNotSupported;
}
