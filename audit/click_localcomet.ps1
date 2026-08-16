param(
    [Parameter(Mandatory = $true)]
    [int]$X,
    [Parameter(Mandatory = $true)]
    [int]$Y,
    [int]$DelayMilliseconds = 500
)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public struct LocalCometClickRect { public int Left; public int Top; public int Right; public int Bottom; }
public static class LocalCometClickNative {
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out LocalCometClickRect rect);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extraInfo);
}
"@

$proc = Get-Process -Name localcomet-desktop -ErrorAction Stop | Select-Object -First 1
$hwnd = [IntPtr]$proc.MainWindowHandle
$rect = New-Object LocalCometClickRect
[LocalCometClickNative]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
[LocalCometClickNative]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 150
[LocalCometClickNative]::SetCursorPos($rect.Left + $X, $rect.Top + $Y) | Out-Null
[LocalCometClickNative]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
[LocalCometClickNative]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds $DelayMilliseconds
Write-Output ("CLICKED relative={0},{1} screen={2},{3} title={4}" -f $X,$Y,($rect.Left+$X),($rect.Top+$Y),$proc.MainWindowTitle)
