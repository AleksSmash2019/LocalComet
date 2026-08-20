#Requires -Version 5.1
<#
  start-local-mcp.ps1  (v2)
  ====================
  Поднимает доступ к локальной машине для Notion AI через MCP — теперь
  ДВА сервера за двумя независимыми туннелями:

    1) FILES  — чтение/запись/правка файлов в РАЗРЕШЁННЫХ папках
                (репозиторий + Obsidian vault)
    2) SHELL  — Desktop Commander: запуск команд, grep по содержимому,
                удаление/перемещение файлов. ПОЛНЫЙ доступ к машине!

  Схема (для каждого сервиса):
    [MCP server (stdio)] -> supergateway (Streamable HTTP, 127.0.0.1)
      -> Cloudflare Quick Tunnel -> публичный HTTPS URL -> вставляешь в Notion

  ЗАПУСК (PowerShell):
    powershell -ExecutionPolicy Bypass -File .\start-local-mcp.ps1
    powershell -ExecutionPolicy Bypass -File .\start-local-mcp.ps1 -NoShell   # только файлы

  СТОП: нажми Enter в окне скрипта (или закрой окно) — все процессы убьются.

  ЧТО НУЖНО: Windows 10/11, Node.js (https://nodejs.org), интернет.
  cloudflared ставится скриптом автоматически через winget.

  БЕЗОПАСНОСТЬ (прочти):
  - Каждый URL содержит свой случайный токен (128 бит) — это и есть "пароль".
    Не публикуй URL никуда.
  - SHELL-URL = ПОЛНЫЙ контроль над этим ПК (выполнение любых команд от
    твоего имени). Держи в секрете вдвойне и останавливай мост сразу после
    работы. Если SHELL не нужен — запускай с -NoShell.
  - FILES ограничен двумя папками: репозиторием и LocalCometVault.
  - Watchdog: раз в 15 сек скрипт проверяет оба звена и перезапускает упавшие.
    Если перезапускается ТУННЕЛЬ — URL МЕНЯЕТСЯ: скрипт напечатает новый,
    его нужно обновить в Notion.
#>

param(
  # Папка, к которой я получу доступ. По умолчанию — репозиторий LocalComet.
  [string]$Folder = "C:\Users\DNS\Documents\LocalComet-build-week-clean",
  # Дополнительные разрешённые папки для FILES (Obsidian vault и т.п.)
  [string[]]$ExtraFolders = @("C:\Users\DNS\Documents\LocalCometVault"),
  [int]$PortFiles = 8765,
  [int]$PortShell = 8766,
  [switch]$NoShell
)

$ErrorActionPreference = "Stop"

# Корректное отображение кириллицы в консоли
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

function Stop-Everything {
  Write-Host ""
  Write-Host "==> Останавливаю туннели и MCP-серверы..."
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "supergateway|server-filesystem|desktop-commander|cloudflared" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Write-Host "==> Всё остановлено. URL больше недоступны."
}

function Test-PortUp([int]$Port) {
  return Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
}

function Wait-PortUp([int]$Port, [int]$Tries) {
  for ($i = 0; $i -lt $Tries; $i++) {
    Start-Sleep -Seconds 2
    if (Test-PortUp $Port) { return $true }
  }
  return $false
}

function Wait-TunnelUrl([string]$LogBase, [int]$Tries) {
  for ($i = 0; $i -lt $Tries; $i++) {
    Start-Sleep -Seconds 2
    $all = ""
    foreach ($f in @($LogBase, "$LogBase.err")) {
      if (Test-Path $f) { $all += (Get-Content $f -Raw -ErrorAction SilentlyContinue) }
    }
    $m = [regex]::Match($all, "https://[a-z0-9-]+\.trycloudflare\.com")
    if ($m.Success) { return $m.Value }
  }
  return $null
}

function Test-McpUrl([string]$Url) {
  try {
    $body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"selftest","version":"1.0"}}}'
    $resp = Invoke-WebRequest -Uri $Url -Method POST -Body $body -ContentType "application/json" -Headers @{ Accept = "application/json, text/event-stream" } -TimeoutSec 25 -UseBasicParsing
    return "OK (HTTP $($resp.StatusCode))"
  } catch {
    return "не удалось: $($_.Exception.Message) — подожди 10 сек и всё равно попробуй URL в Notion"
  }
}

function Get-ShortPath([string]$Path) {
  try {
    $fso = New-Object -ComObject Scripting.FileSystemObject
    $short = $fso.GetFolder($Path).ShortPath
    if ($short) { return $short }
  } catch { }
  return $Path
}

try {
  # ---------- 0. Проверяем папки ----------
  if (-not (Test-Path $Folder)) {
    if ($PSScriptRoot -and (Test-Path $PSScriptRoot)) {
      Write-Host "!! Папка '$Folder' не найдена — использую папку, где лежит скрипт: $PSScriptRoot"
      $Folder = $PSScriptRoot
    } else {
      throw "Папка '$Folder' не найдена. Поправь переменную \$Folder в начале скрипта."
    }
  }
  Write-Host "==> Папка для MCP: $Folder"

  $allowedDirs = @($Folder)
  foreach ($extra in $ExtraFolders) {
    if (Test-Path $extra) {
      $allowedDirs += $extra
      Write-Host "==> Доп. папка для MCP: $extra"
    } else {
      Write-Host "!! Доп. папка '$extra' не найдена — пропускаю (vault не будет доступен)."
    }
  }

  # Короткие пути (8.3), чтобы не ломать кавычки внутри вложенной команды
  $shortDirs = @()
  foreach ($d in $allowedDirs) {
    $short = Get-ShortPath $d
    if ($short -match '[^\x00-\x7F]') {
      throw "В пути '$d' есть кириллица или спецсимволы — cmd-прослойка их не переживёт. Укажи ASCII-путь."
    }
    $shortDirs += $short
  }
  $fsDirArg = $shortDirs -join " "

  # ---------- 1. Node.js ----------
  if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) {
    throw "Node.js не найден (команда npx). Установи LTS с https://nodejs.org и запусти скрипт заново."
  }
  Write-Host "==> Node.js: OK"

  # ---------- 2. cloudflared ----------
  # SECURITY: This explicit script intentionally creates a public quick tunnel
  # for local MCP sharing; the desktop app never launches it implicitly.
  # Do not pass credentials or expose non-local services through this path.
  if (-not (Get-Command cloudflared.exe -ErrorAction SilentlyContinue)) {
    Write-Host "==> cloudflared не найден, ставлю через winget (разреши установку, если спросит)..."
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  }
  if (-not (Get-Command cloudflared.exe -ErrorAction SilentlyContinue)) {
    throw "cloudflared не установился автоматически. Выполни: winget install Cloudflare.cloudflared — и запусти скрипт заново."
  }
  Write-Host "==> cloudflared: OK"

  # ---------- 3. Секретные пути (пароль в URL) — отдельный токен на сервис ----------
  $McpPathFiles = "/mcp-" + [guid]::NewGuid().ToString("N")
  $McpPathShell = "/mcp-" + [guid]::NewGuid().ToString("N")

  $LogDir = Join-Path $env:TEMP "local-mcp"
  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

  $GatewayCmdFiles = Join-Path $LogDir "run-gateway-files.cmd"
  $GatewayLogFiles = Join-Path $LogDir "gateway-files.log"
  $TunnelLogFiles  = Join-Path $LogDir "tunnel-files.log"
  $GatewayCmdShell = Join-Path $LogDir "run-gateway-shell.cmd"
  $GatewayLogShell = Join-Path $LogDir "gateway-shell.log"
  $TunnelLogShell  = Join-Path $LogDir "tunnel-shell.log"
  Remove-Item $GatewayLogFiles, $TunnelLogFiles, "$TunnelLogFiles.err" -ErrorAction SilentlyContinue
  Remove-Item $GatewayLogShell, $TunnelLogShell, "$TunnelLogShell.err" -ErrorAction SilentlyContinue

  # ---------- 4. MCP-мосты: stdio -> Streamable HTTP ----------
  Write-Host "==> Запускаю FILES-сервер на 127.0.0.1:$PortFiles ..."
  @"
@echo off
npx -y supergateway --stdio "npx -y @modelcontextprotocol/server-filesystem $fsDirArg" --outputTransport streamableHttp --port $PortFiles --streamableHttpPath $McpPathFiles > "$GatewayLogFiles" 2>&1
"@ | Set-Content -Path $GatewayCmdFiles -Encoding ascii
  Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$GatewayCmdFiles`"" -WindowStyle Hidden
  if (-not (Wait-PortUp $PortFiles 45)) {
    throw "FILES-сервер не поднялся на порту $PortFiles. Лог: $GatewayLogFiles (частая причина — медленный npx при первой загрузке: просто запусти скрипт ещё раз)."
  }
  Write-Host "==> FILES-сервер: OK"

  if (-not $NoShell) {
    Write-Host "==> Запускаю SHELL-сервер (Desktop Commander) на 127.0.0.1:$PortShell ..."
    @"
@echo off
npx -y supergateway --stdio "npx -y @wonderwhy-er/desktop-commander" --outputTransport streamableHttp --port $PortShell --streamableHttpPath $McpPathShell > "$GatewayLogShell" 2>&1
"@ | Set-Content -Path $GatewayCmdShell -Encoding ascii
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$GatewayCmdShell`"" -WindowStyle Hidden
    if (-not (Wait-PortUp $PortShell 60)) {
      throw "SHELL-сервер не поднялся на порту $PortShell. Лог: $GatewayLogShell (при первой загрузке пакета это может занять пару минут — запусти скрипт ещё раз)."
    }
    Write-Host "==> SHELL-сервер: OK"
  }

  # ---------- 5. Публичные туннели ----------
  Write-Host "==> Поднимаю публичный HTTPS-туннель для FILES..."
  $tunnelProcFiles = Start-Process -FilePath "cloudflared.exe" -ArgumentList "tunnel --url http://127.0.0.1:$PortFiles --no-autoupdate" -RedirectStandardOutput $TunnelLogFiles -RedirectStandardError "$TunnelLogFiles.err" -WindowStyle Hidden -PassThru
  $baseFiles = Wait-TunnelUrl $TunnelLogFiles 30
  if (-not $baseFiles) { throw "Cloudflare не выдал URL для FILES за минуту. Лог: $TunnelLogFiles" }
  $UrlFiles = "$baseFiles$McpPathFiles"

  $UrlShell = $null
  $tunnelProcShell = $null
  if (-not $NoShell) {
    Write-Host "==> Поднимаю публичный HTTPS-туннель для SHELL..."
    $tunnelProcShell = Start-Process -FilePath "cloudflared.exe" -ArgumentList "tunnel --url http://127.0.0.1:$PortShell --no-autoupdate" -RedirectStandardOutput $TunnelLogShell -RedirectStandardError "$TunnelLogShell.err" -WindowStyle Hidden -PassThru
    $baseShell = Wait-TunnelUrl $TunnelLogShell 30
    if (-not $baseShell) { throw "Cloudflare не выдал URL для SHELL за минуту. Лог: $TunnelLogShell" }
    $UrlShell = "$baseShell$McpPathShell"
  }

  # ---------- 6. Самопроверка end-to-end ----------
  Write-Host "==> Проверяю, что серверы отвечают снаружи..."
  $selfFiles = Test-McpUrl $UrlFiles
  $selfShell = if ($NoShell) { "пропущена (-NoShell)" } else { Test-McpUrl $UrlShell }

  Write-Host ""
  Write-Host "=============================================================="
  Write-Host "  ГОТОВО. Два URL — оба секретные, никому не показывай:"
  Write-Host ""
  Write-Host "  FILES (repo + vault, чтение/запись/правка):"
  Write-Host "  $UrlFiles"
  Write-Host ""
  if (-not $NoShell) {
    Write-Host "  SHELL (команды, grep, удаление — ПОЛНЫЙ доступ к ПК!):"
    Write-Host "  $UrlShell"
    Write-Host ""
  }
  Write-Host "  Самопроверка FILES: $selfFiles"
  Write-Host "  Самопроверка SHELL: $selfShell"
  Write-Host "=============================================================="
  Write-Host ""
  Write-Host "Куда вставить в Notion (ДВА отдельных подключения):"
  Write-Host "  Settings -> Connections -> Discover -> Custom MCP server"
  Write-Host "  Добавь оба URL. Имена предложи, например: local-files и local-shell."
  Write-Host ""
  Write-Host "После подключения скажи мне в чате 'мсп подключен' — проверю оба."
  Write-Host ""

  # ---------- 7. Watchdog: держим мост живым до Enter ----------
  $canReadKeys = $true
  try { $null = [Console]::KeyAvailable } catch { $canReadKeys = $false }

  if (-not $canReadKeys) {
    Read-Host "Нажми Enter, чтобы ОСТАНОВИТЬ туннели и MCP-серверы"
  } else {
    Write-Host "Watchdog активен: проверка каждые 15 сек. Нажми Enter, чтобы остановить."
    while ($true) {
      if ([Console]::KeyAvailable) {
        $key = [Console]::ReadKey($true)
        if ($key.Key -eq [ConsoleKey]::Enter) { break }
      }
      Start-Sleep -Seconds 15

      # 7a. Жив ли gateway (локальный порт)?
      if (-not (Test-PortUp $PortFiles)) {
        Write-Host "!! FILES: порт $PortFiles не отвечает — перезапускаю gateway..."
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match "server-filesystem" } |
          ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$GatewayCmdFiles`"" -WindowStyle Hidden
        if (Wait-PortUp $PortFiles 45) { Write-Host "==> FILES: gateway поднялся" } else { Write-Host "!! FILES: не поднялся, лог: $GatewayLogFiles" }
      }
      if (-not $NoShell -and -not (Test-PortUp $PortShell)) {
        Write-Host "!! SHELL: порт $PortShell не отвечает — перезапускаю gateway..."
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match "desktop-commander" } |
          ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$GatewayCmdShell`"" -WindowStyle Hidden
        if (Wait-PortUp $PortShell 60) { Write-Host "==> SHELL: gateway поднялся" } else { Write-Host "!! SHELL: не поднялся, лог: $GatewayLogShell" }
      }

      # 7b. Жив ли туннель? (перезапуск туннеля МЕНЯЕТ URL)
      if ($tunnelProcFiles.HasExited) {
        Write-Host "!! FILES: туннель упал — поднимаю новый..."
        Remove-Item $TunnelLogFiles, "$TunnelLogFiles.err" -ErrorAction SilentlyContinue
        $tunnelProcFiles = Start-Process -FilePath "cloudflared.exe" -ArgumentList "tunnel --url http://127.0.0.1:$PortFiles --no-autoupdate" -RedirectStandardOutput $TunnelLogFiles -RedirectStandardError "$TunnelLogFiles.err" -WindowStyle Hidden -PassThru
        $baseFiles = Wait-TunnelUrl $TunnelLogFiles 30
        if ($baseFiles) {
          $UrlFiles = "$baseFiles$McpPathFiles"
          Write-Host "!!! У FILES НОВЫЙ URL — обнови его в Notion -> Connections:"
          Write-Host "    $UrlFiles"
        } else {
          Write-Host "!! FILES: туннель не поднялся, лог: $TunnelLogFiles"
        }
      }
      if (-not $NoShell -and $tunnelProcShell.HasExited) {
        Write-Host "!! SHELL: туннель упал — поднимаю новый..."
        Remove-Item $TunnelLogShell, "$TunnelLogShell.err" -ErrorAction SilentlyContinue
        $tunnelProcShell = Start-Process -FilePath "cloudflared.exe" -ArgumentList "tunnel --url http://127.0.0.1:$PortShell --no-autoupdate" -RedirectStandardOutput $TunnelLogShell -RedirectStandardError "$TunnelLogShell.err" -WindowStyle Hidden -PassThru
        $baseShell = Wait-TunnelUrl $TunnelLogShell 30
        if ($baseShell) {
          $UrlShell = "$baseShell$McpPathShell"
          Write-Host "!!! У SHELL НОВЫЙ URL — обнови его в Notion -> Connections:"
          Write-Host "    $UrlShell"
        } else {
          Write-Host "!! SHELL: туннель не поднялся, лог: $TunnelLogShell"
        }
      }
    }
  }
}
catch {
  Write-Host ""
  Write-Host "ОШИБКА: $($_.Exception.Message)"
  Write-Host ""
}
finally {
  Stop-Everything
}
