$ErrorActionPreference = 'Stop'
$base = 'C:\Users\DNS\Documents\LocalComet-build-week-clean\desktop\localcomet-desktop'

$gatewayPath = Join-Path $base 'src\lib\stores\modelGateway.ts'
$gateway = Get-Content -Raw -LiteralPath $gatewayPath
$duplicatePattern = "(?s)    if \(!selectedModel\) throw trustPayloadError\(\);\r?\n    const requestedRuntimeId = state\.preferredRuntimeId \?\? readiness\.selected_runtime_id;\r?\n    if \(!requestedRuntimeId\) throw \{ code: 'runtime_not_selected', message: 'No compute engine is selected' \};\r?\n    const trustKind = modelTrustKind\(selectedModel\);"
$duplicateReplacement = "    if (!selectedModel) throw trustPayloadError();`r`n    const trustKind = modelTrustKind(selectedModel);"
$gateway = [regex]::Replace($gateway, $duplicatePattern, $duplicateReplacement, 1)
$gateway = $gateway.Replace('readonly preferredRuntimeId: string | null;', 'readonly preferredRuntimeId?: string | null;')
Set-Content -LiteralPath $gatewayPath -Value $gateway -Encoding utf8

$acquisitionPath = Join-Path $base 'src\lib\stores\artifactAcquisition.ts'
$acquisition = Get-Content -Raw -LiteralPath $acquisitionPath
$acquisition = $acquisition.Replace('export async function setUpManagedModel(modelId: string): Promise<boolean> {', 'export async function setUpManagedModel(modelId: string, runtimeId?: string): Promise<boolean> {')
$acquisition = $acquisition.Replace('  return setUpManagedArtifactsForModel(artifacts, model);`r`n}', '  return setUpManagedArtifactsForModel(artifacts, model, runtimeId);`r`n}')
Set-Content -LiteralPath $acquisitionPath -Value $acquisition -Encoding utf8

Push-Location $base
try { npm run check } finally { Pop-Location }
