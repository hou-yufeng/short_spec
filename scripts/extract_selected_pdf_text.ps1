[CmdletBinding()]
param(
    [string[]]$PdfPaths,
    [string]$PdfListPath,
    [string]$OutDir = "analysis_output/runtime_spec_text",
    [string]$ManifestPath = "analysis_output/runtime_spec_text_manifest.json",
    [int]$RestartWordEvery = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

function Get-ProductName {
    param(
        [string]$BaseName
    )

    if ($BaseName -like "*_Spec") {
        return $BaseName.Substring(0, $BaseName.Length - "_Spec".Length)
    }

    return $BaseName
}

if ([System.IO.Path]::IsPathRooted($OutDir)) {
    $resolvedOutDir = $OutDir
} else {
    $resolvedOutDir = Join-Path (Get-Location) $OutDir
}

if ([System.IO.Path]::IsPathRooted($ManifestPath)) {
    $resolvedManifestPath = $ManifestPath
} else {
    $resolvedManifestPath = Join-Path (Get-Location) $ManifestPath
}
New-Item -ItemType Directory -Force -Path $resolvedOutDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $resolvedManifestPath -Parent) | Out-Null

$inputPdfPaths = @()
if ($PdfPaths) {
    $inputPdfPaths += $PdfPaths
}
if ($PdfListPath) {
    $resolvedListPath = (Resolve-Path $PdfListPath).Path
    $inputPdfPaths += Get-Content -LiteralPath $resolvedListPath | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
}
if ($inputPdfPaths.Count -eq 0) {
    throw "No PDF paths were provided."
}

$resolvedPdfPaths = @()
foreach ($path in $inputPdfPaths) {
    $resolved = (Resolve-Path $path).Path
    if (-not $resolved.ToLower().EndsWith(".pdf")) {
        throw "Only PDF input is supported by this helper: $resolved"
    }
    $resolvedPdfPaths += $resolved
}

$results = New-Object System.Collections.Generic.List[object]
$word = $null
$processedSinceRestart = 0

try {
    $word = New-WordApplication

    foreach ($pdfPath in $resolvedPdfPaths) {
        if ($processedSinceRestart -ge $RestartWordEvery) {
            Close-WordApplication -Word $word
            Start-Sleep -Seconds 1
            $word = New-WordApplication
            $processedSinceRestart = 0
        }

        $file = Get-Item -LiteralPath $pdfPath
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $doc = $null
        try {
            $doc = $word.Documents.Open($pdfPath, $false, $true)
            $text = Normalize-Text -Text $doc.Content.Text
            $product = Get-ProductName -BaseName $file.BaseName
            $outFile = Join-Path $resolvedOutDir ($file.Name + ".txt")
            [System.IO.File]::WriteAllText($outFile, $text, [System.Text.Encoding]::UTF8)

            $results.Add([pscustomobject]@{
                source_pdf = $pdfPath
                file_name = $file.Name
                product = $product
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
    generated_at = (Get-Date).ToString("o")
    output_dir = $resolvedOutDir
    pdf_count = $resolvedPdfPaths.Count
    extractions = $results
}

$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $resolvedManifestPath -Encoding UTF8
Write-Output ("DONE`tPDFs={0}`tManifest={1}" -f $resolvedPdfPaths.Count, $resolvedManifestPath)
