param(
    [string]$InstallDir = 'D:\Smart-Organizer',
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'
$SourceDir = Split-Path -Parent $PSScriptRoot

Write-Host 'Smart Organizer v0.1.0 installer' -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath 'D:\')) {
    Write-Host 'Drive D: was not found. Using Documents\Smart-Organizer.' -ForegroundColor Yellow
    $InstallDir = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Smart-Organizer'
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$exclude = @('data', 'logs', '.update-staging')
Get-ChildItem -LiteralPath $SourceDir -Force |
    Where-Object { $exclude -notcontains $_.Name } |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $InstallDir -Recurse -Force
    }

New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir 'data') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir 'logs') | Out-Null

$exe = Join-Path $InstallDir 'SmartOrganizer.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw "SmartOrganizer.exe was not found after installation: $exe"
}

if (-not $NoShortcut) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'Smart Organizer.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.IconLocation = "$exe,0"
    $shortcut.Description = 'Smart Organizer local file assistant'
    $shortcut.Save()
    Write-Host "Shortcut created: $shortcutPath" -ForegroundColor Green
}

Write-Host "Installed to: $InstallDir" -ForegroundColor Green
Write-Host 'Local data and logs directories are preserved on reinstall.' -ForegroundColor Green
