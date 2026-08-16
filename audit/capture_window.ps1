param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public struct LocalCometRect { public int Left; public int Top; public int Right; public int Bottom; }
public static class LocalCometWindowNative {
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out LocalCometRect rect);
}
"@

$proc = Get-Process -Name localcomet-desktop -ErrorAction Stop | Select-Object -First 1
$hwnd = [IntPtr]$proc.MainWindowHandle
if ($hwnd -eq [IntPtr]::Zero) { throw "LocalComet window handle is zero" }
$rect = New-Object LocalCometRect
if (-not [LocalCometWindowNative]::GetWindowRect($hwnd, [ref]$rect)) { throw "GetWindowRect failed" }
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -le 0 -or $height -le 0) { throw "Invalid window bounds: ${width}x${height}" }
$dir = [IO.Path]::GetDirectoryName($OutputPath)
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
    $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
Write-Output "CAPTURED $OutputPath ${width}x${height} title=$($proc.MainWindowTitle)"
