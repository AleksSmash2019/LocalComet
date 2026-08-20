$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ConsoleSignal {
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool AttachConsole(uint dwProcessId);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool FreeConsole();
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool GenerateConsoleCtrlEvent(uint dwCtrlEvent, uint dwProcessGroupId);
}
'@
$parentPid = 7716
if (-not (Get-Process -Id $parentPid -ErrorAction SilentlyContinue)) { Write-Output 'PARENT_NOT_FOUND'; exit 0 }
if (-not [ConsoleSignal]::AttachConsole([uint32]$parentPid)) {
    throw "AttachConsole failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
}
try {
    if (-not [ConsoleSignal]::GenerateConsoleCtrlEvent(1, [uint32]$parentPid)) {
        throw "GenerateConsoleCtrlEvent failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }
    Write-Output "CTRL_BREAK_SENT_TO_GROUP=$parentPid"
} finally {
    [ConsoleSignal]::FreeConsole() | Out-Null
}
