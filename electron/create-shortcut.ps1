$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\IAM System.lnk")
$Shortcut.TargetPath = "$PSScriptRoot\dist\win-unpacked\IAM System.exe"
$Shortcut.IconLocation = "$PSScriptRoot\icon.ico"
$Shortcut.WorkingDirectory = "$PSScriptRoot\dist\win-unpacked"
$Shortcut.Description = "IAM System - Identity and Access Management"
$Shortcut.Save()

Write-Host "Ярлык создан на рабочем столе с вашей иконкой!" -ForegroundColor Green
