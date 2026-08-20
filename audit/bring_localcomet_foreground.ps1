$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Foreground {
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
}
'@
$p = Get-Process -Name localcomet-desktop -ErrorAction Stop | Select-Object -First 1
$h = [IntPtr]$p.MainWindowHandle
if ($h -eq [IntPtr]::Zero) { throw 'LocalComet has no main window handle' }
[Foreground]::ShowWindowAsync($h, 5) | Out-Null
[Foreground]::SetForegroundWindow($h) | Out-Null
Write-Output "FOREGROUND_PID=$($p.Id) HWND=$h VISIBLE=$([Foreground]::IsWindowVisible($h)) TITLE=$($p.MainWindowTitle)"
