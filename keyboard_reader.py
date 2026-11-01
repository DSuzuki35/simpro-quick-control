"""Optional global Windows shortcuts, using native hotkey messages, not a key hook."""
import copy

KEYS={**{f'Key{chr(n)}':(n,chr(n)) for n in range(65,91)},
      **{f'Digit{n}':(48+n,str(n)) for n in range(10)},
      **{f'F{n}':(111+n,f'F{n}') for n in range(1,25) if n!=12},
      **{f'Numpad{n}':(96+n,f'Num {n}') for n in range(10)},
      'ArrowLeft':(0x25,'Left'),'ArrowUp':(0x26,'Up'),'ArrowRight':(0x27,'Right'),'ArrowDown':(0x28,'Down'),
      'PageUp':(0x21,'Page Up'),'PageDown':(0x22,'Page Down'),'Home':(0x24,'Home'),'End':(0x23,'End'),
      'Insert':(0x2d,'Insert'),'Delete':(0x2e,'Delete'),'Space':(0x20,'Space'),
      'NumpadAdd':(0x6b,'Num +'),'NumpadSubtract':(0x6d,'Num −')}
KEY_OPTIONS=[{'key':key,'label':entry[1]} for key,entry in KEYS.items()]

def validate_shortcut(chord):
    if not isinstance(chord,dict) or set(chord)!={'key','modifiers'}:raise ValueError('Choose a key and modifiers')
    key=chord['key'];modifiers=chord['modifiers']
    if not isinstance(key,str) or key not in KEYS:raise ValueError('Unsupported key (F12 is reserved by Windows)')
    if type(modifiers) is not int or not 0<=modifiers<=7:raise ValueError('Use Ctrl, Alt and/or Shift')
    if not key.startswith('F') and not modifiers&3:raise ValueError('Add Ctrl or Alt, or choose a function key')

def shortcut_label(chord):
    validate_shortcut(chord)
    return '+'.join([name for bit,name in ((2,'Ctrl'),(1,'Alt'),(4,'Shift')) if chord['modifiers']&bit]+[KEYS[chord['key']][1]])

class HotkeyRegistry:
    def __init__(self,register,unregister):
        self.register=register;self.unregister=unregister;self.actions={};self.next_id=1;self.bindings=None;self.errors={}
    def close(self):
        for ident in self.actions:self.unregister(ident)
        self.actions={};self.bindings=None
    def sync(self,bindings,force=False):
        if not force and bindings==self.bindings:return self.errors
        self.close();self.bindings=copy.deepcopy(bindings);self.errors={}
        for action,chord in bindings.items():
            validate_shortcut(chord);ident=self.next_id;self.next_id+=1
            if ident>0xbfff:
                self.errors[action]='Restart the controller to register more shortcuts';continue
            if self.register(ident,chord['modifiers']|0x4000,KEYS[chord['key']][0]):
                self.actions[ident]=(action,copy.deepcopy(chord))
            else:self.errors[action]=shortcut_label(chord)+' is unavailable; another app or Windows may already use it'
        return self.errors

def run_keyboard(service):
    import ctypes
    from ctypes import wintypes
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT];user32.RegisterHotKey.restype=wintypes.BOOL
    user32.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int];user32.UnregisterHotKey.restype=wintypes.BOOL
    user32.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT];user32.PeekMessageW.restype=wintypes.BOOL
    user32.MsgWaitForMultipleObjects.argtypes=[wintypes.DWORD,ctypes.c_void_p,wintypes.BOOL,wintypes.DWORD,wintypes.DWORD];user32.MsgWaitForMultipleObjects.restype=wintypes.DWORD
    registry=HotkeyRegistry(lambda ident,mods,key:bool(user32.RegisterHotKey(None,ident,mods,key)),lambda ident:user32.UnregisterHotKey(None,ident))
    message=wintypes.MSG();revision=-1
    try:
        while not service.stop.is_set():
            with service.lock:
                bindings=copy.deepcopy(service.config['keyboard']);current_revision=service.keyboard_revision
            errors=registry.sync(bindings,force=current_revision!=revision);revision=current_revision
            with service.lock:
                service.keyboard_errors=copy.deepcopy(errors);service.keyboard_active=[entry[0] for entry in registry.actions.values()]
            while user32.PeekMessageW(ctypes.byref(message),None,0,0,1):
                if message.message==0x0312 and message.wParam in registry.actions:
                    action,chord=registry.actions[message.wParam]
                    service.keyboard(action,chord)
            user32.MsgWaitForMultipleObjects(0,None,False,250,0x04ff)
    except Exception as exc:
        with service.lock:service.keyboard_errors={'_system':'Keyboard shortcuts stopped: '+str(exc)};service.keyboard_active=[]
    finally:registry.close()
