$names = @('msedgewebview2.exe','localcomet-desktop.exe')
foreach ($name in $names) {
    Get-CimInstance Win32_Process -Filter ("Name='{0}'" -f $name) |
        Select-Object ProcessId, Name, CommandLine |
        Format-List
}
