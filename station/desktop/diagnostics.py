"""Local, user-invoked Windows inventory. No reader commands, network scans,
print jobs, account details, passwords or automatic uploads.
"""
import json
import os
import subprocess

SCRIPT = r'''
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$ErrorActionPreference = 'Stop'
$stationInventory = [ordered]@{schema_version=2;read_only=$true;system=$null;usb=@();serial_ports=@();serial_devices=@();printers=@();reader_processes=@();legacy_connections=@();errors=@()}
try {
 $stationInventory.system = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,OSArchitecture
} catch { $stationInventory.errors += 'Versione Windows non disponibile' }
try {
 $stationInventory.usb = @(Get-CimInstance Win32_PnPEntity -Filter "PNPDeviceID LIKE 'USB%'" | Select-Object Name,Manufacturer,PNPClass,Service,HardwareID)
} catch { $stationInventory.errors += 'Elenco USB non disponibile' }
try {
 $stationInventory.serial_ports = @(Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description)
} catch { $stationInventory.errors += 'Elenco porte seriali non disponibile' }
try {
 # Win32_SerialPort alone can omit USB serial and direct-access FTDI devices.
 # Read the existing PnP configuration; never open a COM port or load a reader DLL.
 $stationSerialDevices = @(Get-CimInstance Win32_PnPEntity -Filter "PNPClass='Ports' OR Service='FTDIBUS' OR Service='FTSER2K'")
 foreach ($stationDevice in $stationSerialDevices) {
  $stationPortName = $null
  $stationBusDescription = $null
  try {
   $stationDeviceKey = 'Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\' + $stationDevice.PNPDeviceID + '\Device Parameters'
   $stationPortName = (Get-ItemProperty -LiteralPath $stationDeviceKey -Name PortName -ErrorAction Stop).PortName
  } catch { }
  try {
   $stationBusDescription = (Get-PnpDeviceProperty -InstanceId $stationDevice.PNPDeviceID -KeyName 'DEVPKEY_Device_BusReportedDeviceDesc' -ErrorAction Stop).Data
  } catch { }
  $stationInventory.serial_devices += [pscustomobject]@{
   Name=$stationDevice.Name;Manufacturer=$stationDevice.Manufacturer;PNPClass=$stationDevice.PNPClass
   Service=$stationDevice.Service;HardwareID=@($stationDevice.HardwareID);PortName=$stationPortName;BusDescription=$stationBusDescription
  }
 }
} catch { $stationInventory.errors += 'Associazione dispositivi seriali non disponibile' }
try {
 $stationInventory.printers = @(Get-CimInstance Win32_Printer | Select-Object Name,DriverName,PortName,Local,Network)
} catch { $stationInventory.errors += 'Elenco stampanti non disponibile' }
try {
 $stationLegacyProcesses = @(Get-Process | Where-Object { $_.ProcessName -match 'new.?pod|newport|lettura|sort|uhf|rfid|reader|antenn|^np[._-]' })
 foreach ($stationProcess in $stationLegacyProcesses) {
  $stationProcessInfo = [ordered]@{Name=$stationProcess.ProcessName;Id=$stationProcess.Id;ProductName=$null;ProductVersion=$null;CompanyName=$null;ReaderModules=@();ModuleScan='unavailable'}
  try {
   $stationFileInfo = $stationProcess.MainModule.FileVersionInfo
   $stationProcessInfo.ProductName = $stationFileInfo.ProductName
   $stationProcessInfo.ProductVersion = $stationFileInfo.ProductVersion
   $stationProcessInfo.CompanyName = $stationFileInfo.CompanyName
  } catch { }
  try {
   $stationProcessInfo.ReaderModules = @($stationProcess.Modules | Where-Object { $_.ModuleName -match 'ftd2xx|feig|id.?isc|impinj|llrp|thingmagic|mercury|rfid|uhf|reader|serial|io\.ports' } | ForEach-Object {
    [pscustomobject]@{Name=$_.ModuleName;CompanyName=$_.FileVersionInfo.CompanyName;ProductName=$_.FileVersionInfo.ProductName;ProductVersion=$_.FileVersionInfo.ProductVersion}
   })
   $stationProcessInfo.ModuleScan = 'ok'
  } catch { }
  $stationInventory.reader_processes += [pscustomobject]$stationProcessInfo
 }
 $stationLegacyIds = @($stationLegacyProcesses | Select-Object -ExpandProperty Id)
 if ($stationLegacyIds.Count -gt 0) {
  $stationInventory.legacy_connections = @(Get-NetTCPConnection -State Established | Where-Object { $stationLegacyIds -contains $_.OwningProcess } | Select-Object OwningProcess,RemoteAddress,RemotePort)
 }
} catch { $stationInventory.errors += 'Connessioni del programma di lettura non disponibili' }
$stationInventory | ConvertTo-Json -Depth 8
'''


def collect(runner=subprocess.run):
    if os.name != 'nt':
        return {'schema_version':2,'read_only':True,'system':None,'usb':[],'serial_ports':[],
                'serial_devices':[],'printers':[],'reader_processes':[],
                'legacy_connections':[],'errors':['Rilevazione disponibile su Windows.']}
    result=runner(['powershell.exe','-NoProfile','-NonInteractive','-Command',SCRIPT],
                  capture_output=True,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise RuntimeError('Windows non ha completato la rilevazione. Nessun dispositivo è stato modificato.')
    report=json.loads(result.stdout.decode('utf-8-sig'))
    if report.get('schema_version')!=2 or report.get('read_only') is not True:
        raise RuntimeError('Risposta della rilevazione non valida.')
    return report
