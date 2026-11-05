"""Install only this station executable and its current-user Windows startup entry."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def application_name(kind):
    if kind not in ('sporco', 'pulito'):
        raise ValueError('Tipo di postazione non valido')
    return 'Sporco' if kind == 'sporco' else 'Pulito'


def install(kind):
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        raise RuntimeError('Usa l’eseguibile Windows compilato per installare l’avvio automatico.')
    import winreg
    name = application_name(kind)
    directory = Path(os.environ['LOCALAPPDATA']) / 'Programs' / 'GestoreLavanderia' / name
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (name + '.exe')
    source = Path(sys.executable).resolve()
    if source != target.resolve():
        shutil.copy2(source, target)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        winreg.SetValueEx(key, 'GestoreLavanderia-' + name, 0, winreg.REG_SZ, subprocess.list2cmdline([str(target)]))
    return target


def disable(kind):
    if os.name != 'nt':
        raise RuntimeError('Funzione disponibile su Windows.')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        try:
            winreg.DeleteValue(key, 'GestoreLavanderia-' + application_name(kind))
        except FileNotFoundError:
            pass
