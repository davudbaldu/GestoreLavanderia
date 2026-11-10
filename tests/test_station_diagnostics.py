"""Exercise the Windows inventory script against synthetic PnP providers."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'station'))
from desktop.diagnostics import SCRIPT


@unittest.skipUnless(os.name == 'nt', 'PowerShell provider fixture runs on Windows')
class WindowsDiagnosticsTests(unittest.TestCase):
    def test_usb_serial_missing_from_win32_serialport_is_identified_via_pnp(self):
        fixture = r'''
function Get-CimInstance {
 [CmdletBinding()] param($ClassName,$Filter)
 switch ($ClassName) {
  'Win32_OperatingSystem' { [pscustomobject]@{Caption='Fixture Windows';Version='10.0';OSArchitecture='64-bit'} }
  'Win32_PnPEntity' {
   if ($Filter -like 'PNPDeviceID*') {
    [pscustomobject]@{Name='USB Serial Converter';Manufacturer='Fixture';PNPClass='USB';Service='FTDIBUS';HardwareID=@('USB\VID_0403&PID_6001');PNPDeviceID='USB\FIXTURE'}
   } else {
    [pscustomobject]@{Name='USB Serial Port (COM42)';Manufacturer='Fixture';PNPClass='Ports';Service='FTSER2K';HardwareID=@('FTDIBUS\COMPORT');PNPDeviceID='FTDIBUS\FIXTURE'}
   }
  }
  'Win32_SerialPort' { }
  'Win32_Printer' { }
  default { throw 'Unexpected provider' }
 }
}
function Get-ItemProperty {
 [CmdletBinding()] param($LiteralPath,$Name)
 [pscustomobject]@{PortName='COM42'}
}
function Get-PnpDeviceProperty {
 [CmdletBinding()] param($InstanceId,$KeyName)
 [pscustomobject]@{Data='Fixture serial interface'}
}
function Get-Process {
 [CmdletBinding()] param()
 $fixtureVersion=[pscustomobject]@{CompanyName='Fixture vendor';ProductName='Fixture reader';ProductVersion='1.2.3'}
 [pscustomobject]@{ProcessName='NewPod.Sort';Id=42;MainModule=[pscustomobject]@{FileVersionInfo=$fixtureVersion};Modules=@([pscustomobject]@{ModuleName='ftd2xx.dll';FileVersionInfo=$fixtureVersion})}
}
function Get-NetTCPConnection {
 [CmdletBinding()] param($State)
 [pscustomobject]@{OwningProcess=42;RemoteAddress='192.0.2.1';RemotePort=1234}
}
'''
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', fixture + SCRIPT],
            capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        report = json.loads(result.stdout.decode('utf-8-sig'))
        self.assertEqual(report['schema_version'], 2)
        self.assertTrue(report['read_only'])
        self.assertEqual(report['serial_ports'], [])
        self.assertEqual(report['serial_devices'][0]['PortName'], 'COM42')
        self.assertEqual(report['serial_devices'][0]['BusDescription'], 'Fixture serial interface')
        self.assertNotIn('PNPDeviceID', report['serial_devices'][0])
        process = report['reader_processes'][0]
        self.assertEqual(process['Name'], 'NewPod.Sort')
        self.assertEqual(process['ReaderModules'][0]['Name'], 'ftd2xx.dll')
        self.assertEqual(process['ModuleScan'], 'ok')
        self.assertEqual(report['legacy_connections'][0]['RemoteAddress'], '192.0.2.1')
        self.assertEqual(report['errors'], [])


if __name__ == '__main__':
    unittest.main()
