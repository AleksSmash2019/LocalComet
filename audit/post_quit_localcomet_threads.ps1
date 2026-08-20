$ErrorActionPreference = 'Stop'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class ThreadQuit {
  [DllImport("user32.dll", SetLastError=true)] public static extern bool PostThreadMessage(uint idThread, uint msg, IntPtr wParam, IntPtr lParam);
}
'@
$targetProcess = Get-Process -Id 30392 -ErrorAction Stop
$threads = @($targetProcess.Threads | ForEach-Object { [uint32]$_.Id })
if ($threads.Count -eq 0) { Write-Output 'NO_THREADS'; exit 0 }
foreach ($threadId in $threads) {
    if ([ThreadQuit]::PostThreadMessage($threadId, 0x0012, [IntPtr]::Zero, [IntPtr]::Zero)) {
        Write-Output "WM_QUIT_POSTED_THREAD=$threadId"
    }
}
