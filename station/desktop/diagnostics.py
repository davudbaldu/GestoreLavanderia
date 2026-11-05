"""Local, user-invoked Windows inventory. No reader commands, network scans,
print jobs, account details, passwords or automatic uploads.
"""
import json
import os
import subprocess

SCRIPT = r'''
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$ErrorActionPreference = 'Stop'
$stationInventory = [ordered]@{schema_version=1;read_only=$true;usb=@();serial_ports=@();printers=@();legacy_connections=@();errors=@()}
try {
 $stationInventory.usb = @(Get-CimInstance Win32_PnPEntity -Filter "PNPDeviceID LIKE 'USB%'" | Select-Object Name,Manufacturer,PNPClass,Service,HardwareID)
} catch { $stationInventory.errors += 'Elenco USB non disponibile' }
try {
 $stationInventory.serial_ports = @(Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description)
} catch { $stationInventory.errors += 'Elenco porte seriali non disponibile' }
try {
 $stationInventory.printers = @(Get-CimInstance Win32_Printer | Select-Object Name,DriverName,PortName,Local,Network)
} catch { $stationInventory.errors += 'Elenco stampanti non disponibile' }
try {
 $stationLegacyIds = @(Get-Process | Where-Object { $_.ProcessName -match '^(NewPod|Sort|LetturaSporco|Lettura|NPSort)$' } | Select-Object -ExpandProperty Id)
 if ($stationLegacyIds.Count -gt 0) {
  $stationInventory.legacy_connections = @(Get-NetTCPConnection -State Established | Where-Object { $stationLegacyIds -contains $_.OwningProcess } | Select-Object OwningProcess,RemoteAddress,RemotePort)
 }
} catch { $stationInventory.errors += 'Connessioni del programma di lettura non disponibili' }
$stationInventory | ConvertTo-Json -Depth 6
'''


def collect(runner=subprocess.run):
    if os.name != 'nt':
        return {'schema_version':1,'read_only':True,'usb':[],'serial_ports':[],
                'printers':[],'legacy_connections':[],'errors':['Rilevazione disponibile su Windows.']}
    result=runner(['powershell.exe','-NoProfile','-NonInteractive','-Command',SCRIPT],
                  capture_output=True,timeout=35,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise RuntimeError('Windows non ha completato la rilevazione. Nessun dispositivo è stato modificato.')
    report=json.loads(result.stdout.decode('utf-8-sig'))
    if report.get('schema_version')!=1 or report.get('read_only') is not True:
        raise RuntimeError('Risposta della rilevazione non valida.')
    return report
