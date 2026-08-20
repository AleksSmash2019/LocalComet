$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class TaoQuit {
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool PostThreadMessage(uint idThread, uint msg, IntPtr wParam, IntPtr lParam);
}
'@
$targetHwnd = [IntPtr]786926
$targetPid = 0
$threadId = [TaoQuit]::GetWindowThreadProcessId($targetHwnd, [ref]$targetPid)
if ($targetPid -ne 32444) { throw "Target HWND PID mismatch: $targetPid" }
if (-not [TaoQuit]::PostThreadMessage($threadId, 0x0012, [IntPtr]::Zero, [IntPtr]::Zero)) {
    throw "PostThreadMessage(WM_QUIT) failed Win32=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
}
Write-Output "WM_QUIT_POSTED_THREAD=$threadId PID=$targetPid"
