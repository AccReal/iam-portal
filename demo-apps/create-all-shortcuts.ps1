# PowerShell script to create desktop shortcuts for all demo applications
# plus the IAM Portal itself (which the apps require for login).

$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [System.Environment]::GetFolderPath('Desktop')

# Get current directory (demo-apps/)
$CurrentDir = Get-Location
$RepoRoot = Split-Path -Parent $CurrentDir

Write-Host "Creating desktop shortcuts for all applications..."
Write-Host ""

# IAM Portal — required for SSO, so it goes first.
$ShortcutPath = "$Desktop\IAM Portal.lnk"
$TargetPath = "$RepoRoot\electron\dist\win-unpacked\IAM System.exe"
if (Test-Path $TargetPath) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = "$RepoRoot\electron\dist\win-unpacked"
    $Shortcut.IconLocation = "$RepoRoot\electron\icon.png"
    $Shortcut.Save()
    Write-Host "Created: IAM Portal.lnk"
} else {
    Write-Host "! IAM Portal not built yet: $TargetPath"
    Write-Host "  Build with: cd ..\electron; npm install; npm run build:win"
}

# CRM System
$ShortcutPath = "$Desktop\CRM Система.lnk"
$TargetPath = "$CurrentDir\crm-app\dist\win-unpacked\CRM Система.exe"
if (Test-Path $TargetPath) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = "$CurrentDir\crm-app\dist\win-unpacked"
    $Shortcut.IconLocation = "$CurrentDir\crm-app\icon.png"
    $Shortcut.Save()
    Write-Host "Created: CRM System.lnk"
} else {
    Write-Host "✗ Not found: $TargetPath"
}

# Corporate Mail
$ShortcutPath = "$Desktop\Корпоративная почта.lnk"
$TargetPath = "$CurrentDir\mail-app\dist\win-unpacked\Корпоративная почта.exe"
if (Test-Path $TargetPath) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = "$CurrentDir\mail-app\dist\win-unpacked"
    $Shortcut.IconLocation = "$CurrentDir\mail-app\icon.png"
    $Shortcut.Save()
    Write-Host "Created: Corporate Mail.lnk"
} else {
    Write-Host "✗ Not found: $TargetPath"
}

# 1C Accounting
$ShortcutPath = "$Desktop\1С Бухгалтерия.lnk"
$TargetPath = "$CurrentDir\1c-app\dist\win-unpacked\1С Бухгалтерия.exe"
if (Test-Path $TargetPath) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = "$CurrentDir\1c-app\dist\win-unpacked"
    $Shortcut.IconLocation = "$CurrentDir\1c-app\icon.png"
    $Shortcut.Save()
    Write-Host "Created: 1C Accounting.lnk"
} else {
    Write-Host "✗ Not found: $TargetPath"
}

# Warehouse
$ShortcutPath = "$Desktop\Склад.lnk"
$TargetPath = "$CurrentDir\warehouse-app\dist\win-unpacked\Склад.exe"
if (Test-Path $TargetPath) {
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $TargetPath
    $Shortcut.WorkingDirectory = "$CurrentDir\warehouse-app\dist\win-unpacked"
    $Shortcut.IconLocation = "$CurrentDir\warehouse-app\icon.png"
    $Shortcut.Save()
    Write-Host "Created: Warehouse.lnk"
} else {
    Write-Host "✗ Not found: $TargetPath"
}

Write-Host ""
Write-Host "=========================================="
Write-Host "All shortcuts created on desktop!"
Write-Host ""
Write-Host "Now you can:"
Write-Host "1. Double-click any application icon"
Write-Host "2. If not logged in, it will prompt you to open the IAM Portal"
Write-Host "3. Log in (or register) in the IAM Portal, pass MFA"
Write-Host "4. The app window will refresh automatically — no re-login needed"
Write-Host "5. Every other demo-app on this machine shares the same session"
Write-Host "=========================================="
