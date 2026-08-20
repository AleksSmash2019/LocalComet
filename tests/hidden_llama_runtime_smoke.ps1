# LocalComet hidden runtime smoke test.
# Starts a separate llama-server on loopback only, sends three OpenAI-compatible
# chat requests, and always terminates only the process it created. No window is
# shown and no LocalComet process, model file, or managed artifact is modified.
param(
    [int]$Port = 18081,
    [int]$ReadyTimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'

function Find-FirstFile {
    param([string]$Root, [string]$Filter)
    Get-ChildItem $Root -Recurse -Force -File -Filter $Filter -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Invoke-Chat {
    param([object[]]$Messages)
    $payload = @{
        model = 'localcomet-hidden-qwen-1.7b'
        messages = $Messages
        temperature = 0
        max_tokens = 64
        stream = $false
        # Qwen3 otherwise may consume a short smoke budget in an internal
        # reasoning trace and return no final assistant content.
        chat_template_kwargs = @{ enable_thinking = $false }
    } | ConvertTo-Json -Depth 8
    $response = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/v1/chat/completions" -ContentType 'application/json' -Body $payload -TimeoutSec 90
    $content = [string]$response.choices[0].message.content
    if ([string]::IsNullOrWhiteSpace($content)) {
        throw 'chat_completion_empty_content'
    }
    return $content
}

$model = Find-FirstFile "$env:LOCALAPPDATA\LocalComet\models" '*1.7B*.gguf'
$server = Find-FirstFile "$env:LOCALAPPDATA\LocalComet" 'llama-server.exe'
if (-not $model) { throw 'qwen_1_7b_model_not_found' }
if (-not $server) { throw 'llama_server_not_found' }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "test_port_in_use:$Port"
}

$logId = [guid]::NewGuid().ToString('N')
$stdoutLogPath = Join-Path $env:TEMP "localcomet-hidden-llama-smoke-$logId.stdout.log"
$stderrLogPath = Join-Path $env:TEMP "localcomet-hidden-llama-smoke-$logId.stderr.log"
$serverProcess = $null
$timer = [System.Diagnostics.Stopwatch]::StartNew()

try {
    # CPU-only makes the test isolated from any active managed Vulkan/GPU runtime.
    $serverProcess = Start-Process -FilePath $server.FullName -ArgumentList @(
        '--model', $model.FullName,
        '--host', '127.0.0.1',
        '--port', $Port,
        '--ctx-size', '2048',
        '--n-gpu-layers', '0'
    ) -WindowStyle Hidden -RedirectStandardOutput $stdoutLogPath -RedirectStandardError $stderrLogPath -PassThru

    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if ($serverProcess.HasExited) { throw "llama_server_exited_early:$($serverProcess.ExitCode)" }
        try {
            $health = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
            if ($health) { $ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 750
        }
    }
    if (-not $ready) { throw 'llama_server_readiness_timeout' }

    $first = Invoke-Chat @(@{ role = 'user'; content = 'Reply with a short greeting for a local AI runtime.' })
    $continued = Invoke-Chat @(
        @{ role = 'user'; content = 'Reply with a short greeting for a local AI runtime.' },
        @{ role = 'assistant'; content = $first },
        @{ role = 'user'; content = 'Now answer with one short sentence explaining that the conversation continues.' }
    )
    $fresh = Invoke-Chat @(@{ role = 'user'; content = 'This is a new chat. Reply with one short confirmation sentence.' })

    [pscustomobject]@{
        ok = $true
        profile = 'isolated_cpu_qwen_1_7b'
        port = $Port
        first_response_characters = $first.Length
        continued_response_characters = $continued.Length
        new_chat_response_characters = $fresh.Length
        elapsed_seconds = [math]::Round($timer.Elapsed.TotalSeconds, 2)
        stdout_log = $stdoutLogPath
        stderr_log = $stderrLogPath
    } | ConvertTo-Json -Compress
} finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
        $serverProcess.WaitForExit()
    }
}
