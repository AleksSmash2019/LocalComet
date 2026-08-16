$ErrorActionPreference = 'Stop'
$base = 'C:\Users\DNS\Documents\LocalComet-build-week-clean\desktop\localcomet-desktop'
$url = 'https://8767-ipwy8zfrdyxknouh9uqzn-1b6e851f.us2.manus.computer'

function Download-Source([string]$name, [string]$target) {
  $tmp = Join-Path $env:TEMP ("localcomet-" + $name)
  & curl.exe --retry 8 --retry-delay 2 --retry-all-errors -L --fail ($url + '/' + $name) -o $tmp
  if ($LASTEXITCODE -ne 0) { throw "Download failed: $name" }
  Copy-Item -Force $tmp (Join-Path $base $target)
}

Download-Source 'ModelManagerSection.svelte' 'src\lib\components\model\ModelManagerSection.svelte'
Download-Source 'ru.ts' 'src\lib\i18n\ru.ts'
Download-Source 'en.ts' 'src\lib\i18n\en.ts'

$path = Join-Path $base 'src\lib\components\model\ModelManagerSection.svelte'
$text = Get-Content -Raw -LiteralPath $path
$replacements = @(
  @(
    "    setManagedSelectedModel,`r`n    stopSelectedManagedRuntime",
    "    setManagedSelectedModel,`r`n    setManagedPreferredRuntime,`r`n    stopSelectedManagedRuntime"
  ),
  @(
    "  `$: runtimes = `$managedRuntimeStore.runtimeCatalog ?? [];`r`n  `$: runtime = runtimes.find((r) => r.variant === 'vulkan') ?? runtimes[0] ?? null;`r`n  `$: modelArtifacts = `$artifactAcquisitionStore.artifacts.filter((artifact) => artifact.kind === 'model');",
    "  `$: runtimes = `$managedRuntimeStore.runtimeCatalog ?? [];`r`n  `$: selectedRuntimeId = `$managedRuntimeStore.preferredRuntimeId`r`n    ?? `$managedRuntimeStore.readiness?.selected_runtime_id`r`n    ?? runtimes.find((candidate) => candidate.variant === 'cpu')?.runtime_id`r`n    ?? runtimes[0]?.runtime_id`r`n    ?? '';`r`n  `$: runtime = runtimes.find((candidate) => candidate.runtime_id === selectedRuntimeId) ?? runtimes[0] ?? null;`r`n  `$: modelArtifacts = `$artifactAcquisitionStore.artifacts.filter((artifact) => artifact.kind === 'model');"
  ),
  @(
    "  `$: runtimeArtifact = `$artifactAcquisitionStore.artifacts.find((artifact): artifact is ApprovedDownloadableArtifact => artifact.kind === 'runtime' && artifact.artifact_id === 'llama-cpp-windows-x86-64-vulkan-bootstrap')`r`n    ?? `$artifactAcquisitionStore.artifacts.find((artifact): artifact is ApprovedDownloadableArtifact => artifact.kind === 'runtime')`r`n    ?? null;`r`n  `$: runtimeInstalled = runtimes.some((item) => installationState(item.runtime_id) === 'valid');",
    "  `$: runtimeArtifact = selectedRuntimeId`r`n    ? `$artifactAcquisitionStore.artifacts.find((artifact): artifact is ApprovedDownloadableArtifact => artifact.kind === 'runtime' && artifact.artifact_id === selectedRuntimeId) ?? null`r`n    : null;`r`n  `$: runtimeInstalled = selectedRuntimeId !== '' && installationState(selectedRuntimeId) === 'valid';"
  ),
  @(
    '          await setUpManagedModel(modelId);',
    '          await setUpManagedModel(modelId, selectedRuntimeId || undefined);'
  ),
  @(
    "  function onModelChange(event: Event) {`r`n    const value = (event.currentTarget as HTMLSelectElement).value;`r`n    selectedModelId = value;`r`n    void setManagedSelectedModel(value);`r`n  }`r`n",
    "  function onModelChange(event: Event) {`r`n    const value = (event.currentTarget as HTMLSelectElement).value;`r`n    selectedModelId = value;`r`n    void setManagedSelectedModel(value);`r`n  }`r`n`r`n  function onRuntimeChange(event: Event) {`r`n    const value = (event.currentTarget as HTMLSelectElement).value;`r`n    setManagedPreferredRuntime(value);`r`n  }`r`n"
  ),
  @(
    "    </dl>`r`n  </div>`r`n`r`n  <div class=\"artifact-card\">`r`n    <div class=\"artifact-heading\">`r`n      <div>`r`n        <span class=\"artifact-kind\">{$t('models.model')}</span>",
    "    </dl>`r`n    <label class=\"runtime-selector\">`r`n      <span>{$t('models.engine_variant')}</span>`r`n      <select`r`n        value={selectedRuntimeId}`r`n        disabled={$managedConnectionBusy || ['Ready', 'Starting', 'Validating', 'Stopping'].includes($managedRuntimeStore.status?.state ?? '')}`r`n        onchange={onRuntimeChange}`r`n      >`r`n        {#each runtimes as item}`r`n          <option value={item.runtime_id}>{$t(`models.variant.${item.variant}`)} · {displayState(installationState(item.runtime_id))}</option>`r`n        {/each}`r`n      </select>`r`n      <small>{$t('models.engine_variant_hint')}</small>`r`n    </label>`r`n    {#if $managedRuntimeStore.status?.state === 'Ready'}`r`n      <p class=\"runtime-selector-hint\">{$t('models.engine_requires_disconnect')}</p>`r`n    {/if}`r`n  </div>`r`n`r`n  <div class=\"artifact-card\">`r`n    <div class=\"artifact-heading\">`r`n      <div>`r`n        <span class=\"artifact-kind\">{$t('models.model')}</span>"
  ),
  @(
    "  .runtime-variants { padding-top: var(--lc-space-2); border-top: var(--border-thin); }`r`n  dt { color: var(--lc-muted); }",
    "  .runtime-variants { padding-top: var(--lc-space-2); border-top: var(--border-thin); }`r`n  .runtime-selector { display: grid; gap: 6px; padding-top: var(--lc-space-2); border-top: var(--border-thin); }`r`n  .runtime-selector > span { color: var(--lc-muted); font-size: 11px; font-weight: 700; }`r`n  .runtime-selector select { width: 100%; min-width: 0; }`r`n  .runtime-selector small, .runtime-selector-hint { margin: 0; color: var(--lc-muted); font-size: 10px; line-height: 1.4; }`r`n  dt { color: var(--lc-muted); }"
  )
)
foreach ($pair in $replacements) {
  if (-not $text.Contains($pair[0])) { throw "Expected source fragment not found in ModelManagerSection.svelte" }
  $text = $text.Replace($pair[0], $pair[1])
}
Set-Content -LiteralPath $path -Value $text -Encoding utf8

Push-Location $base
try { npm run check } finally { Pop-Location }
