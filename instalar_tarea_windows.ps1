# Programa SkyCheck para que corra todos los días en tu compu (Windows).
# Uso: clic derecho -> "Ejecutar con PowerShell", o:
#   powershell -ExecutionPolicy Bypass -File instalar_tarea_windows.ps1
# Para cambiar la hora, editá $Hora. Para borrar la tarea:
#   Unregister-ScheduledTask -TaskName SkyCheck -Confirm:$false
$Hora   = "09:00"
$Dir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Action = New-ScheduledTaskAction -Execute "$Dir\correr.bat" -WorkingDirectory $Dir
$Trigger = New-ScheduledTaskTrigger -Daily -At $Hora
# StartWhenAvailable: si la compu estaba apagada a esa hora, corre apenas se prenda.
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName "SkyCheck" -Action $Action -Trigger $Trigger -Settings $Settings -Force
Write-Host "Listo: SkyCheck va a correr todos los dias a las $Hora."
