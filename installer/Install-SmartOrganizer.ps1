param(
    [string]$InstallDir = "D:\Smart-Organizer"
)

$ErrorActionPreference = "Stop"
$SourceDir = Split-Path -Parent $PSScriptRoot
Write-Host "Smart Organizer v0.1.0" -ForegroundColor Cyan

if (-not (Test-Path "D:\")) {
    Write-Host "Диск D: не найден. Используется папка Documents\Smart-Organizer." -ForegroundColor Yellow
    $InstallDir = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Smart-Organizer"
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$exclude = @("data", "logs", ".update-staging")
Get-ChildItem -LiteralPath $SourceDir -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $InstallDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "logs") | Out-Null

$exe = Join-Path $InstallDir "SmartOrganizer.exe"
if (-not (Test-Path $exe)) {
    $exe = Join-Path $InstallDir "SmartOrganizer.cmd"
}
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Smart Organizer.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $InstallDir
$icon = Join-Path $InstallDir "SmartOrganizer.exe"
if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
$shortcut.Description = "Smart Organizer — умный локальный помощник файлов"
$shortcut.Save()
Write-Host "Установлено: $InstallDir" -ForegroundColor Green
Write-Host "Ярлык создан: $shortcutPath" -ForegroundColor Green
