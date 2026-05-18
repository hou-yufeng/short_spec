[CmdletBinding()]
param(
    [string]$SourceDir = "trainning_data",
    [string]$OutDir = "analysis_output/extracted_text",
    [string]$ManifestPath = "analysis_output/extraction_manifest.json",
    [int]$RestartWordEvery = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ProductInfo {
    param(
        [string]$BaseName
    )

    if ($BaseName -like "*_ShortDesc_AutoLayout") {
        return @{
            Product = $BaseName.Substring(0, $BaseName.Length - "_ShortDesc_AutoLayout".Length)
            Kind = "shortdesc"
        }
    }

    if ($BaseName -like "*_Spec") {
        return @{
            Product = $BaseName.Substring(0, $BaseName.Length - "_Spec".Length)
            Kind = "spec"
        }
    }

    throw "Unsupported PDF naming pattern: $BaseName"
}

function New-WordApplication {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    return $word
}

function Close-WordApplication {
    param(
        [Parameter(Mandatory = $true)]
        $Word
    )

    if ($null -ne $Word) {
        $Word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($Word)
    }
}

function Normalize-Text {
    param(
        [string]$Text
    )

    $normalized = $Text.Replace("`r`n", "`n").Replace("`r", "`n")
    $normalized = $normalized.Replace([string][char]7, "")
    return $normalized
}

$resolvedSourceDir = (Resolve-Path $SourceDir).Path
$resolvedOutDir = Join-Path (Get-Location) $OutDir
$resolvedManifestPath = Join-Path (Get-Location) $ManifestPath

New-Item -ItemType Directory -Force -Path $resolvedOutDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $resolvedManifestPath -Parent) | Out-Null

$pdfFiles = Get-ChildItem -Path $resolvedSourceDir -File | Where-Object { $_.Extension -match '^\.(?i:pdf)$' } | Sort-Object FullName
if ($pdfFiles.Count -eq 0) {
    throw "No PDF files found in $resolvedSourceDir"
}

$pairMap = @{}
foreach ($file in $pdfFiles) {
    $info = Get-ProductInfo -BaseName $file.BaseName
    if (-not $pairMap.ContainsKey($info.Product)) {
        $pairMap[$info.Product] = @{
            Product = $info.Product
            Spec = $null
            ShortDesc = $null
        }
    }

    switch ($info.Kind) {
        "spec" { $pairMap[$info.Product].Spec = $file.FullName }
        "shortdesc" { $pairMap[$info.Product].ShortDesc = $file.FullName }
    }
}

$missingPairs = @()
foreach ($entry in $pairMap.Values | Sort-Object Product) {
    if ([string]::IsNullOrWhiteSpace($entry.Spec) -or [string]::IsNullOrWhiteSpace($entry.ShortDesc)) {
        $missingPairs += [pscustomobject]@{
            product = $entry.Product
            has_spec = -not [string]::IsNullOrWhiteSpace($entry.Spec)
            has_shortdesc = -not [string]::IsNullOrWhiteSpace($entry.ShortDesc)
        }
    }
}

if ($missingPairs.Count -gt 0) {
    $missingPairs | ConvertTo-Json -Depth 5 | Write-Output
    throw "Found products without complete Spec/ShortDesc pairs."
}

$results = New-Object System.Collections.Generic.List[object]
$word = $null
$processedSinceRestart = 0

try {
    $word = New-WordApplication

    foreach ($file in $pdfFiles) {
        if ($processedSinceRestart -ge $RestartWordEvery) {
            Close-WordApplication -Word $word
            Start-Sleep -Seconds 1
            $word = New-WordApplication
            $processedSinceRestart = 0
        }

        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $doc = $null
        try {
            $doc = $word.Documents.Open($file.FullName, $false, $true)
            $text = Normalize-Text -Text $doc.Content.Text
            $outFile = Join-Path $resolvedOutDir ($file.Name + ".txt")
            [System.IO.File]::WriteAllText($outFile, $text, [System.Text.Encoding]::UTF8)

            $results.Add([pscustomobject]@{
                file_name = $file.Name
                full_path = $file.FullName
                product = (Get-ProductInfo -BaseName $file.BaseName).Product
                kind = (Get-ProductInfo -BaseName $file.BaseName).Kind
                output_txt = $outFile
                char_count = $text.Length
                elapsed_seconds = [math]::Round($sw.Elapsed.TotalSeconds, 3)
            })
        }
        finally {
            if ($null -ne $doc) {
                $doc.Close()
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
            }
            $sw.Stop()
        }

        $processedSinceRestart += 1
        Write-Output ("EXTRACTED`t{0}`t{1}`t{2}" -f $file.Name, $text.Length, [math]::Round($sw.Elapsed.TotalSeconds, 2))
    }
}
finally {
    if ($null -ne $word) {
        Close-WordApplication -Word $word
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$manifest = [pscustomobject]@{
    source_dir = $resolvedSourceDir
    output_dir = $resolvedOutDir
    manifest_generated_at = (Get-Date).ToString("o")
    pdf_count = $pdfFiles.Count
    pair_count = $pairMap.Count
    products = ($pairMap.Keys | Sort-Object)
    extractions = $results
}

$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $resolvedManifestPath -Encoding UTF8
Write-Output ("DONE`tPDFs={0}`tPairs={1}`tManifest={2}" -f $pdfFiles.Count, $pairMap.Count, $resolvedManifestPath)
