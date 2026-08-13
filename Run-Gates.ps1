# Run-Gates.ps1 - LocalComet full-functional gate runner with Markdown report.
# ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8 .ps1 without BOM.
# Check-only: never deletes files, never rewrites evidence.
# scripts/refresh_evidence.py is intentionally NOT part of this runner.
#
# Coverage:
#   1. Frontend gates (npm run check, npm test)
#   2. Rust gates (cargo fmt --check, cargo test, cargo clippy -D warnings)
#   3. scripts/check_*.py checkers        (auto-discovered)
#   4. tests/test_*.py suites             (auto-discovered)
#   5. tools/test_*.py regression suites  (auto-discovered)
#   6. CLI smoke (scripts/smoke_test.py --mode=cli)
#   7. Real-sidecar gate when LOCALCOMET_REQUIRE_REAL_SIDECAR=1
#   8. Legacy root flow tests only with -IncludeLegacy; reported as INFO and
#      never affect the verdict (legacy CLI is not part of the MVP product).
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File .\Run-Gates.ps1
#   powershell -ExecutionPolicy Bypass -File .\Run-Gates.ps1 -FailFast
#   powershell -ExecutionPolicy Bypass -File .\Run-Gates.ps1 -IncludeLegacy
#
# Report: artifacts\gate-reports\gate-report-<timestamp>.md
# Full logs: artifacts\gate-reports\logs\
# Exit code: 0 if all product gates pass, 1 otherwise.

param(
    [switch]$FailFast,
    [switch]$IncludeLegacy
)

$ErrorActionPreference = 'Continue'
$TailLines = 40

$RepoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = Join-Path $RepoRoot 'desktop\localcomet-desktop'
$RustDir    = Join-Path $DesktopDir 'src-tauri'
$ReportDir  = Join-Path $RepoRoot 'artifacts\gate-reports'
$LogDir     = Join-Path $ReportDir 'logs'
New-Item -ItemType Directory -Force -Path $ReportDir, $LogDir | Out-Null

$timestamp  = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$reportPath = Join-Path $ReportDir ("gate-report-" + $timestamp + ".md")

$Python = 'python'
if ($env:LOCALCOMET_TEST_PYTHON) { $Python = $env:LOCALCOMET_TEST_PYTHON }

# Excluded from tools discovery: requires external OpenAI credentials,
# so it is not a deterministic local gate. Run it manually when configured.
# We also exclude the 4 main-style v684 gates here since we explicitly run them below.
$ToolsExclude = @(
    'test_gpt_bridge.py',
    'test_v6841_desktop_ipc.py',
    'test_v6842_desktop_shell.py',
    'test_v6843_sidecar_supervisor.py',
    'test_v6844_control_plane.py'
)
# Excluded from check discovery: env-gated below, not part of default discovery.
$CheckExclude = @('check_real_sidecar_tests.py')

$gates = New-Object System.Collections.Generic.List[hashtable]

function Add-Gate {
    param(
        [string]$Name,
        [string]$WorkDir,
        [string]$Cmd,
        [string[]]$CmdArgs,
        [bool]$Info
    )
    $gates.Add(@{ Name = $Name; WorkDir = $WorkDir; Cmd = $Cmd; Args = $CmdArgs; Info = $Info })
}

# 1. Frontend gates
Add-Gate 'npm run check'         $DesktopDir 'npm'   @('run','check') $false
Add-Gate 'npm test'              $DesktopDir 'npm'   @('test') $false

# 2. Rust gates
Add-Gate 'cargo fmt --check'     $RustDir    'cargo' @('fmt','--check') $false
Add-Gate 'cargo test'            $RustDir    'cargo' @('test') $false
Add-Gate 'cargo clippy -D warnings' $RustDir 'cargo' @('clippy','--all-targets','--all-features','--','-D','warnings') $false

# 3. Checkers (auto-discovered)
$scriptsDir = Join-Path $RepoRoot 'scripts'
if (Test-Path $scriptsDir) {
    Get-ChildItem -Path $scriptsDir -Filter 'check_*.py' -File | Sort-Object Name | ForEach-Object {
        if ($CheckExclude -notcontains $_.Name) {
            Add-Gate ('check: ' + $_.Name) $RepoRoot $Python @('scripts/' + $_.Name) $false
        }
    }
}

# 4. tests/ suites (auto-discovered)
$testsDir = Join-Path $RepoRoot 'tests'
if (Test-Path $testsDir) {
    Get-ChildItem -Path $testsDir -Filter 'test_*.py' -File | Sort-Object Name | ForEach-Object {
        Add-Gate ('test: ' + $_.Name) $RepoRoot $Python @('tests/' + $_.Name) $false
    }
}

# 5. tools/ regression suites (auto-discovered)
$toolsDir = Join-Path $RepoRoot 'tools'
if (Test-Path $toolsDir) {
    Get-ChildItem -Path $toolsDir -Filter 'test_*.py' -File | Sort-Object Name | ForEach-Object {
        if ($ToolsExclude -notcontains $_.Name) {
            Add-Gate ('tools: ' + $_.Name) $RepoRoot $Python @('tools/' + $_.Name) $false
        }
    }
}

# 5a. Orphan v6.84.x main-style gates
Add-Gate 'tools: test_v6841_desktop_ipc.py' $RepoRoot $Python @('tools/test_v6841_desktop_ipc.py') $false
Add-Gate 'tools: test_v6842_desktop_shell.py' $RepoRoot $Python @('tools/test_v6842_desktop_shell.py') $false
Add-Gate 'tools: test_v6843_sidecar_supervisor.py' $RepoRoot $Python @('tools/test_v6843_sidecar_supervisor.py') $false
Add-Gate 'tools: test_v6844_control_plane.py' $RepoRoot $Python @('tools/test_v6844_control_plane.py') $false

# 6. CLI smoke
Add-Gate 'smoke_test --mode=cli' $RepoRoot $Python @('scripts/smoke_test.py','--mode=cli') $false

# 7. Real-sidecar gate (explicit env opt-in; needs system Python)
if ($env:LOCALCOMET_REQUIRE_REAL_SIDECAR -eq '1') {
    Add-Gate 'check_real_sidecar_tests' $RepoRoot $Python @('scripts/check_real_sidecar_tests.py') $false
}

# 8. Legacy root flow tests (INFO only; legacy CLI is outside the MVP product)
if ($IncludeLegacy) {
    Get-ChildItem -Path $RepoRoot -Filter 'test_*.py' -File | Sort-Object Name | ForEach-Object {
        Add-Gate ('legacy: ' + $_.Name) $RepoRoot $Python @($_.Name) $true
    }
}

function Invoke-Gate {
    param(
        [hashtable]$Gate,
        [int]$Index
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $output = ''
    $exitCode = -1
    Push-Location $Gate.WorkDir
    try {
        $output = & $Gate.Cmd @($Gate.Args) 2>&1 | Out-String -Width 4096
        $exitCode = $LASTEXITCODE
    } catch {
        $output += "`n[runner exception] " + $_.Exception.Message
        $exitCode = -1
    }
    Pop-Location
    $sw.Stop()

    $passed = ($exitCode -eq 0)
    $safeName = $Gate.Name -replace '[^A-Za-z0-9_.-]', '_'
    $logName = ("{0:d2}-{1}.log" -f $Index, $safeName)
    $logPath = Join-Path $LogDir $logName
    $logHeader = "gate: " + $Gate.Name + "`ncmd: " + $Gate.Cmd + " " + ($Gate.Args -join ' ') + "`nworkdir: " + $Gate.WorkDir + "`nexit: " + $exitCode + "`nseconds: " + [math]::Round($sw.Elapsed.TotalSeconds, 1) + "`n---`n"
    [System.IO.File]::WriteAllText($logPath, $logHeader + $output, (New-Object System.Text.UTF8Encoding($true)))

    return [PSCustomObject]@{
        Name     = $Gate.Name
        CmdLine  = $Gate.Cmd + ' ' + ($Gate.Args -join ' ')
        WorkDir  = $Gate.WorkDir
        ExitCode = $exitCode
        Seconds  = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        Passed   = $passed
        Info     = $Gate.Info
        Tail     = (($output -split "`r?`n") | Select-Object -Last $TailLines) -join "`n"
        LogFile  = 'logs/' + $logName
    }
}

$gitHead   = ''
$gitBranch = ''
$gitStatus = ''
try {
    Push-Location $RepoRoot
    $gitHead   = (& git rev-parse HEAD 2>&1 | Out-String).Trim()
    $gitBranch = (& git rev-parse --abbrev-ref HEAD 2>&1 | Out-String).Trim()
    $gitStatus = (& git status --short 2>&1 | Out-String).Trim()
    Pop-Location
} catch {
    $gitHead = 'unavailable'
}

$results = New-Object System.Collections.Generic.List[object]
$index = 0
foreach ($gate in $gates) {
    $index++
    Write-Host ("[" + $index + "/" + $gates.Count + "] " + $gate.Name + " ...")
    $r = Invoke-Gate -Gate $gate -Index $index
    $results.Add($r)
    $tag = ''
    if ($r.Info) { $tag = ' [INFO]' }
    if ($r.Passed) {
        Write-Host ("    PASS" + $tag + " (" + $r.Seconds + "s)")
    } else {
        Write-Host ("    FAIL" + $tag + " exit=" + $r.ExitCode + " (" + $r.Seconds + "s)  log: " + $r.LogFile)
    }
    if ($FailFast -and -not $r.Passed -and -not $r.Info) { break }
}

$productResults = @($results | Where-Object { -not $_.Info })
$infoResults    = @($results | Where-Object { $_.Info })
$failed  = @($productResults | Where-Object { -not $_.Passed })
$infoFailed = @($infoResults | Where-Object { -not $_.Passed })

$verdict = 'PASS'
if ($failed.Count -gt 0) { $verdict = 'FAIL' }

$md = New-Object System.Collections.Generic.List[string]
$md.Add('# LocalComet Gate Report')
$md.Add('')
$md.Add('- Timestamp: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
$md.Add('- Repo: ' + $RepoRoot)
$md.Add('- Branch: ' + $gitBranch)
$md.Add('- HEAD: ' + $gitHead)
$md.Add('- Python: ' + $Python)
$md.Add('- Product gates: ' + $productResults.Count + ' (' + @($productResults | Where-Object { $_.Passed }).Count + ' pass, ' + $failed.Count + ' fail)')
if ($infoResults.Count -gt 0) {
    $md.Add('- Legacy INFO gates: ' + $infoResults.Count + ' (' + $infoFailed.Count + ' failing, informational only)')
}
$md.Add('- Verdict: **' + $verdict + '**')
$md.Add('')
$md.Add('## Git status --short (initial state)')
$md.Add('')
$md.Add('```')
if ($gitStatus) { $md.Add($gitStatus) } else { $md.Add('(clean)') }
$md.Add('```')
$md.Add('')
$md.Add('## Summary (product gates)')
$md.Add('')
$md.Add('| # | Gate | Exit | Seconds | Result |')
$md.Add('|---|------|------|---------|--------|')
$i = 0
foreach ($r in $productResults) {
    $i++
    $mark = 'PASS'
    if (-not $r.Passed) { $mark = 'FAIL' }
    $md.Add('| ' + $i + ' | ' + $r.Name + ' | ' + $r.ExitCode + ' | ' + $r.Seconds + ' | ' + $mark + ' |')
}
$md.Add('')
if ($infoResults.Count -gt 0) {
    $md.Add('## Summary (legacy INFO gates; do not affect the verdict)')
    $md.Add('')
    $md.Add('| # | Gate | Exit | Seconds | Result |')
    $md.Add('|---|------|------|---------|--------|')
    $i = 0
    foreach ($r in $infoResults) {
        $i++
        $mark = 'PASS'
        if (-not $r.Passed) { $mark = 'FAIL' }
        $md.Add('| ' + $i + ' | ' + $r.Name + ' | ' + $r.ExitCode + ' | ' + $r.Seconds + ' | ' + $mark + ' |')
    }
    $md.Add('')
}
foreach ($r in $results) {
    $mark = 'PASS'
    if (-not $r.Passed) { $mark = 'FAIL' }
    $infoTag = ''
    if ($r.Info) { $infoTag = ' [INFO]' }
    $md.Add('## ' + $mark + $infoTag + ' - ' + $r.Name)
    $md.Add('')
    $md.Add('- cmd: `' + $r.CmdLine + '`')
    $md.Add('- workdir: `' + $r.WorkDir + '`')
    $md.Add('- exit: ' + $r.ExitCode + ', seconds: ' + $r.Seconds)
    $md.Add('- full log: `' + $r.LogFile + '`')
    $md.Add('')
    $md.Add('Last ' + $TailLines + ' lines (verbatim):')
    $md.Add('')
    $md.Add('```')
    $md.Add($r.Tail.TrimEnd())
    $md.Add('```')
    $md.Add('')
}
$md.Add('## Notes')
$md.Add('')
$md.Add('- scripts/refresh_evidence.py was NOT run: this runner is check-only and must not rewrite evidence.')
$md.Add('- check_real_sidecar_tests.py runs only with LOCALCOMET_REQUIRE_REAL_SIDECAR=1 and LOCALCOMET_TEST_PYTHON pointing at system Python.')
$md.Add('- tools/test_gpt_bridge.py is excluded: it requires external OpenAI credentials.')
$md.Add('- Legacy root flow tests run only with -IncludeLegacy and never affect the verdict.')

[System.IO.File]::WriteAllText($reportPath, ($md -join "`n"), (New-Object System.Text.UTF8Encoding($true)))

Write-Host ''
Write-Host ('Report: ' + $reportPath)
Write-Host ('Verdict: ' + $verdict)

if ($verdict -eq 'PASS') { exit 0 } else { exit 1 }
