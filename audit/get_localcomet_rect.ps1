Add-Type @"
using System;
using System.Runtime.InteropServices;
public struct LocalCometProbeRect { public int Left; public int Top; public int Right; public int Bottom; }
public static class LocalCometProbeNative {
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out LocalCometProbeRect rect);
}
"@
$proc = Get-Process -Name localcomet-desktop -ErrorAction Stop | Select-Object -First 1
$rect = New-Object LocalCometProbeRect
[LocalCometProbeNative]::GetWindowRect([IntPtr]$proc.MainWindowHandle, [ref]$rect) | Out-Null
Write-Output ("HANDLE={0} RECT={1},{2},{3},{4} SIZE={5}x{6}" -f $proc.MainWindowHandle,$rect.Left,$rect.Top,$rect.Right,$rect.Bottom,($rect.Right-$rect.Left),($rect.Bottom-$rect.Top))
