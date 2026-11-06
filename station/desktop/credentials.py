"""Windows-user DPAPI protection. Never fall back to plaintext token storage."""
import ctypes
import os
from pathlib import Path
from ctypes import wintypes


class _Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data, protect):
    if os.name != 'nt':
        raise RuntimeError('Il salvataggio sicuro della sessione richiede Windows.')
    buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = _Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if protect:
        function = crypt32.CryptProtectData
        function.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        ok = function(ctypes.byref(source), 'Gestore Lavanderia', None, None, None, 1, ctypes.byref(target))
    else:
        function = crypt32.CryptUnprotectData
        function.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        ok = function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class TokenStore:
    def __init__(self, directory):
        self.path = Path(directory) / 'session.dpapi'

    def save(self, token):
        encrypted = _crypt(token.encode('utf-8'), True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_bytes(encrypted)
        temporary.replace(self.path)

    def load(self):
        return _crypt(self.path.read_bytes(), False).decode('utf-8') if self.path.exists() else None

    def clear(self):
        self.path.unlink(missing_ok=True)
