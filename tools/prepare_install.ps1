$ErrorActionPreference = 'Stop'
$portRoot = Split-Path -Parent $PSScriptRoot
$installRoot = Join-Path $portRoot 'original'
$stageRoot = Join-Path $portRoot 'prepared'
$moduleRoot = Join-Path $portRoot 'build\relocated-audio'
$metadata = Get-Content -LiteralPath (Join-Path $moduleRoot 'preparation.json') -Raw | ConvertFrom-Json
$expectedExe = 'cd885d84bcbdacddc27bdbd6676e376557f118f090e71e0db7c746e72c949064'
if ((Get-FileHash -LiteralPath (Join-Path $installRoot 'gta_sa.exe') -Algorithm SHA256).Hash.ToLower() -ne $expectedExe) { throw 'Original executable checksum differs' }
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $installRoot 'gta_sa.exe') -Destination (Join-Path $stageRoot 'gta_sa.exe')
foreach ($module in $metadata.modules) {
    $moduleSource = Join-Path $moduleRoot $module.name
    if ((Get-FileHash -LiteralPath $moduleSource -Algorithm SHA256).Hash.ToLower() -ne $module.prepared_sha256) { throw "Prepared module changed: $($module.name)" }
    Copy-Item -LiteralPath $moduleSource -Destination (Join-Path $stageRoot $module.name)
}
foreach ($assetDir in Get-ChildItem -LiteralPath $installRoot -Directory) {
    $assetLink = Join-Path $stageRoot $assetDir.Name
    if (-not (Test-Path -LiteralPath $assetLink)) {
        New-Item -ItemType Junction -Path $assetLink -Target $assetDir.FullName | Out-Null
    } elseif ((Get-Item -LiteralPath $assetLink).LinkType -ne 'Junction') {
        throw "Existing asset path is not a junction: $assetLink"
    }
}
foreach ($resource in Get-ChildItem -LiteralPath $installRoot -File) {
    if ($resource.Extension -notin @('.exe', '.dll')) {
        Copy-Item -LiteralPath $resource.FullName -Destination (Join-Path $stageRoot $resource.Name)
    }
}
if ((Get-FileHash -LiteralPath (Join-Path $stageRoot 'gta_sa.exe') -Algorithm SHA256).Hash.ToLower() -ne $expectedExe) { throw 'Staged executable checksum differs' }
Write-Output "Prepared installation at $stageRoot. Original EXE retained byte-for-byte; assets linked; audio DLL copies use separate bases."
