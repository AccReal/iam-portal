# PowerShell script to create desktop shortcuts for all demo applications
# Fixed version with proper encoding

$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [System.Environment]::GetFolderPath('Desktop')
$CurrentDir = (Get-Location).Path

Write-Host "Creating desktop shortcuts for all applications..."
Write-Host ""

# Find all .exe files in dist folders
$apps = @(
    @{Name="CRM Система"; Path="crm-app\dist\win-unpacked\CRM Система.exe"},
    @{Name="Корпоративная почта"; Path="mail-app\dist\win-unpacked\Корпоративная почта.exe"},
    @{Name="1С Бухгалтерия"; Path="1c-app\dist\win-unpacked\1С Бухгалтерия.exe"},
    @{Name="Склад"; Path="warehouse-app\dist\win-unpacked\Склад.exe"}
)

foreach ($app in $apps) {
    $ShortcutPath = Join-Path $Desktop "$($app.Name).lnk"
    $TargetPath = Join-Path $CurrentDir $app.Path
    
    if (Test-Path $TargetPath) {
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = $TargetPath
        $Shortcut.WorkingDirectory = Split-Path $TargetPath
        $Shortcut.Save()
        Write-Host "Created: $($app.Name).lnk"
    } else {
        Write-Host "Not found: $TargetPath"
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host "All shortcuts created on desktop!"
Write-Host ""
Write-Host "Now you can:"
Write-Host "1. Double-click any application icon"
Write-Host "2. It will ask you to login"
Write-Host "3. Login through IAM System"
Write-Host "4. Application will open automatically"
Write-Host "5. All other apps will also work without re-login!"
Write-Host "=========================================="
