[CmdletBinding()]
param(
    [string]$SourceDir = "trainning_data",
    [string]$Glob = "*_Spec.PDF",
    [string]$OutputXlsx = "analysis_output/all_shortspecs_rule_based.xlsx",
    [ValidateSet("per_product", "single_sheet_summary")]
    [string]$WorkbookLayout = "per_product",
    [ValidateSet("auto", "psref_wrapped", "content_only")]
    [string]$OutputMode = "auto",
    [ValidateSet("modern", "legacy")]
    [string]$HeadingStyle = "modern",
    [switch]$PassThru
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SourceDir = $SourceDir.Trim().Trim('"')
$OutputXlsx = $OutputXlsx.Trim().Trim('"')
if ($SourceDir.EndsWith("\")) {
    $SourceDir = "$SourceDir."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonScript = Join-Path $repoRoot "scripts\batch_generate_shortspec_excel_rule_based.py"
$resolvedSourceDir = if ([System.IO.Path]::IsPathRooted($SourceDir)) {
    (Resolve-Path $SourceDir).Path
} else {
    (Resolve-Path (Join-Path $repoRoot $SourceDir)).Path
}
$resolvedOutputXlsx = if ([System.IO.Path]::IsPathRooted($OutputXlsx)) { $OutputXlsx } else { Join-Path $repoRoot $OutputXlsx }

if (-not (Test-Path -LiteralPath $pythonScript)) {
    throw "Python script not found: $pythonScript"
}
if (-not (Test-Path -LiteralPath $resolvedSourceDir)) {
    throw "Source directory not found: $resolvedSourceDir"
}

$specFiles = @(Get-ChildItem -LiteralPath $resolvedSourceDir -File | Where-Object { $_.Name -like $Glob } | Sort-Object Name)
if ($specFiles.Count -eq 0) {
    throw "No spec files matched '$Glob' under $resolvedSourceDir"
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
    "--output-mode",
    $OutputMode,
    "--heading-style",
    $HeadingStyle
)

Write-Output ("SOURCE_DIR`t{0}" -f $resolvedSourceDir)
Write-Output ("GLOB`t{0}" -f $Glob)
Write-Output ("MATCHED_SPEC_FILES`t{0}" -f $specFiles.Count)
Write-Output ("OUTPUT_XLSX`t{0}" -f $resolvedOutputXlsx)
Write-Output ("MODE`trule_based")
Write-Output ("WORKBOOK_LAYOUT`t{0}" -f $WorkbookLayout)
Write-Output ("OUTPUT_MODE`t{0}" -f $OutputMode)
Write-Output ("HEADING_STYLE`t{0}" -f $HeadingStyle)

& $pythonCommand[0] $pythonCommand[1..($pythonCommand.Count - 1)]
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "Rule-based batch generation failed with exit code $exitCode"
}

if ($PassThru) {
    [pscustomobject]@{
        source_dir = $resolvedSourceDir
        glob = $Glob
        matched_spec_files = $specFiles.Count
        output_xlsx = $resolvedOutputXlsx
        mode = "rule_based"
        workbook_layout = $WorkbookLayout
        output_mode = $OutputMode
        heading_style = $HeadingStyle
    }
}
