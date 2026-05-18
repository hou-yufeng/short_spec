[CmdletBinding()]
param(
    [string]$SourceDir = "trainning_data",
    [string]$Glob = "*_Spec.PDF",
    [string]$OutputXlsx = "analysis_output/all_shortspecs.xlsx",
    [string]$SystemPromptFile = "prompts/spec_to_shortdesc_v7_system.txt",
    [ValidateSet("per_product", "single_sheet_summary")]
    [string]$WorkbookLayout = "per_product",
    [string]$Model = "gpt-5.4",
    [ValidateSet("none", "minimal", "low", "medium", "high", "xhigh")]
    [string]$ReasoningEffort = "high",
    [int]$MaxOutputTokens = 6000,
    [int]$TimeoutSeconds = 300,
    [string]$ApiKeyEnv = "OPENAI_API_KEY",
    [string]$MockShortdescDir = "",
    [switch]$PassThru
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonScript = Join-Path $repoRoot "scripts\batch_generate_shortspec_excel.py"
$resolvedSourceDir = if ([System.IO.Path]::IsPathRooted($SourceDir)) {
    (Resolve-Path $SourceDir).Path
} else {
    (Resolve-Path (Join-Path $repoRoot $SourceDir)).Path
}
$resolvedOutputXlsx = if ([System.IO.Path]::IsPathRooted($OutputXlsx)) { $OutputXlsx } else { Join-Path $repoRoot $OutputXlsx }
$resolvedPromptFile = if ([System.IO.Path]::IsPathRooted($SystemPromptFile)) { $SystemPromptFile } else { Join-Path $repoRoot $SystemPromptFile }
$resolvedMockDir = if ([string]::IsNullOrWhiteSpace($MockShortdescDir)) {
    $null
} elseif ([System.IO.Path]::IsPathRooted($MockShortdescDir)) {
    $MockShortdescDir
} else {
    Join-Path $repoRoot $MockShortdescDir
}

if (-not (Test-Path -LiteralPath $pythonScript)) {
    throw "Python script not found: $pythonScript"
}
if (-not (Test-Path -LiteralPath $resolvedSourceDir)) {
    throw "Source directory not found: $resolvedSourceDir"
}
if (-not (Test-Path -LiteralPath $resolvedPromptFile)) {
    throw "Prompt file not found: $resolvedPromptFile"
}
if ($resolvedMockDir -and -not (Test-Path -LiteralPath $resolvedMockDir)) {
    throw "Mock shortdesc directory not found: $resolvedMockDir"
}

$specFiles = @(Get-ChildItem -LiteralPath $resolvedSourceDir -File | Where-Object { $_.Name -like $Glob } | Sort-Object Name)
if ($specFiles.Count -eq 0) {
    throw "No spec files matched '$Glob' under $resolvedSourceDir"
}

if (-not $resolvedMockDir -and [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($ApiKeyEnv))) {
    throw "$ApiKeyEnv is not set. Set it before running, or use -MockShortdescDir for offline validation."
}

New-Item -ItemType Directory -Force -Path (Split-Path $resolvedOutputXlsx -Parent) | Out-Null

$pythonCommand = @(
    "python",
    $pythonScript,
    "--spec-dir",
    $resolvedSourceDir,
    "--glob",
    $Glob,
    "--output-xlsx",
    $resolvedOutputXlsx,
    "--workbook-layout",
    $WorkbookLayout,
    "--system-prompt-file",
    $resolvedPromptFile,
    "--model",
    $Model,
    "--reasoning-effort",
    $ReasoningEffort,
    "--max-output-tokens",
    $MaxOutputTokens.ToString(),
    "--timeout-seconds",
    $TimeoutSeconds.ToString(),
    "--api-key-env",
    $ApiKeyEnv
)

if ($resolvedMockDir) {
    $pythonCommand += @("--mock-shortdesc-dir", $resolvedMockDir)
}

Write-Output ("SOURCE_DIR`t{0}" -f $resolvedSourceDir)
Write-Output ("GLOB`t{0}" -f $Glob)
Write-Output ("MATCHED_SPEC_FILES`t{0}" -f $specFiles.Count)
Write-Output ("OUTPUT_XLSX`t{0}" -f $resolvedOutputXlsx)
Write-Output ("MODE`t{0}" -f $(if ($resolvedMockDir) { "mock" } else { "responses_api" }))
Write-Output ("WORKBOOK_LAYOUT`t{0}" -f $WorkbookLayout)
Write-Output ("MODEL`t{0}" -f $Model)

& $pythonCommand[0] $pythonCommand[1..($pythonCommand.Count - 1)]
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "Batch generation failed with exit code $exitCode"
}

if ($PassThru) {
    [pscustomobject]@{
        source_dir = $resolvedSourceDir
        glob = $Glob
        matched_spec_files = $specFiles.Count
        output_xlsx = $resolvedOutputXlsx
        mode = if ($resolvedMockDir) { "mock" } else { "responses_api" }
        workbook_layout = $WorkbookLayout
        model = $Model
    }
}
