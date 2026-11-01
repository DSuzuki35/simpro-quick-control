"""Per-user, opt-in Windows login startup; no admin rights required."""
import sys
import winreg

KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME='SimPro Quick Control'

def command():
    if not getattr(sys,'frozen',False):return ''
    return '"'+sys.executable+'" --startup'

def enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY) as key:value,_=winreg.QueryValueEx(key,NAME)
        return value==command()
    except OSError:return False

def set_enabled(value):
    if type(value) is not bool:raise ValueError('Startup must be on or off')
    if value and not command():raise ValueError('Use the packaged executable to enable Windows startup')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,KEY) as key:
        if value:winreg.SetValueEx(key,NAME,0,winreg.REG_SZ,command())
        else:
            try:winreg.DeleteValue(key,NAME)
            except FileNotFoundError:pass
