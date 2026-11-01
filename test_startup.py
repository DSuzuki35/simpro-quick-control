import sys
from unittest.mock import MagicMock
import pytest
import startup

def test_startup_quotes_executable_and_starts_quietly(monkeypatch):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'executable',r'C:\My App\SimPro Quick Control.exe')
    assert startup.command()=='"C:\\My App\\SimPro Quick Control.exe" --startup'

def test_source_mode_cannot_register_python_as_startup(monkeypatch):
    monkeypatch.delattr(sys,'frozen',raising=False)
    with pytest.raises(ValueError):startup.set_enabled(True)

def test_registry_opt_in_and_removal_are_scoped(monkeypatch):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    registry=MagicMock();monkeypatch.setattr(startup,'winreg',registry)
    handle=registry.CreateKey.return_value.__enter__.return_value
    startup.set_enabled(True)
    registry.CreateKey.assert_called_with(registry.HKEY_CURRENT_USER,startup.KEY)
    registry.SetValueEx.assert_called_with(handle,startup.NAME,0,registry.REG_SZ,startup.command())
    startup.set_enabled(False)
    registry.DeleteValue.assert_called_once_with(handle,startup.NAME)
