$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Collections.Generic;
using System.Text;
using System.Runtime.InteropServices;
public static class WindowProbe {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int maxCount);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder text, int maxCount);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
  public static List<IntPtr> ForProcess(uint pid) {
    var result = new List<IntPtr>();
    EnumWindows((hWnd, lParam) => { uint actual; GetWindowThreadProcessId(hWnd, out actual); if (actual == pid) result.Add(hWnd); return true; }, IntPtr.Zero);
    return result;
  }
  public static string Description(IntPtr hWnd) {
    var title = new StringBuilder(512); var cls = new StringBuilder(256);
    GetWindowText(hWnd, title, title.Capacity); GetClassName(hWnd, cls, cls.Capacity);
    return String.Format("HWND={0} VISIBLE={1} CLASS={2} TITLE={3}", hWnd, IsWindowVisible(hWnd), cls, title);
  }
}
'@
$targetPid = 30392
$windows = [WindowProbe]::ForProcess([uint32]$targetPid)
if ($windows.Count -eq 0) { Write-Output "NO_TOP_LEVEL_WINDOWS_FOR_PID=$targetPid"; exit 0 }
foreach ($hWnd in $windows) {
    Write-Output ([WindowProbe]::Description($hWnd))
    if ([WindowProbe]::PostMessage($hWnd, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)) {
        Write-Output "WM_CLOSE_SENT=$hWnd"
    } else {
        Write-Output "WM_CLOSE_FAILED=$hWnd"
    }
}
