"""Lightweight native popup without an embedded browser process."""
import ctypes
import logging
from pathlib import Path
import sys
import threading
import webbrowser

def run_desktop(service,server,url,data_dir):
    import tkinter as tk
    import pystray
    from PIL import Image
    root=tk.Tk();root.withdraw();root.title('SimPro Quick Control')
    root.resizable(False,False);root.attributes('-topmost',True)
    root.configure(bg='#191c20');root.geometry('430x250+80+80')
    assets=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'web'
    root.iconbitmap(str(assets/'icon.ico'))
    user32=ctypes.windll.user32
    user32.GetParent.argtypes=[ctypes.c_void_p];user32.GetParent.restype=ctypes.c_void_p
    user32.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]
    user32.GetForegroundWindow.restype=ctypes.c_void_p
    user32.IsWindowVisible.argtypes=[ctypes.c_void_p]
    user32.GetWindowLongPtrW.argtypes=[ctypes.c_void_p,ctypes.c_int];user32.GetWindowLongPtrW.restype=ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_ssize_t];user32.SetWindowLongPtrW.restype=ctypes.c_ssize_t
    user32.SetWindowPos.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
    native={'manual_hide_at':None,'visible':False,'signature':None}
    def open_settings():webbrowser.open(url)
    def hide():native['manual_hide_at']=service.menu_status()[1]
    root.protocol('WM_DELETE_WINDOW',hide)
    def quit_app():service.stop.set();service.wake.set()
    server.open_settings=open_settings;server.hide_menu=hide;server.quit_app=quit_app
    def background(fn):threading.Thread(target=fn,daemon=True).start()
    def adjust(direction):
        def work():
            try:service.adjust(service.state()['config']['selected'],direction)
            except Exception:pass
        background(work)
    def cycle(direction):
        state=service.state();keys=[k for k in state['config']['cycle'] if k in state['values']]
        if not keys:return
        selected=state['config']['selected'];index=keys.index(selected) if selected in keys else 0
        service.update_config({'selected':keys[(index+direction)%len(keys)]})
    def label(text,size=12,color='#f3f4f5'):
        return tk.Label(root,text=text,font=('Segoe UI',size),bg='#191c20',fg=color,anchor='w')
    group=label('BASIC',9,'#ffb05a');group.place(x=22,y=14)
    status=label('PAUSED',9,'#aab2bc');status.place(x=232,y=14)
    title=label('FFB strength',16);title.place(x=22,y=43)
    value=label('—',42);value.place(x=19,y=72)
    secondary=label('Connecting to SimPro…',10,'#ffb05a');secondary.place(x=22,y=145)
    meter=tk.Canvas(root,width=386,height=3,bg='#353b43',highlightthickness=0);meter.place(x=22,y=179)
    fill=meter.create_rectangle(0,0,0,3,fill='#ffb05a',outline='')
    def button(text,command,x,y,width=36):
        b=tk.Button(root,text=text,command=command,bg='#282e35',fg='#f3f4f5',activebackground='#424950',activeforeground='#fff',bd=0,font=('Segoe UI',13),takefocus=False)
        b.place(x=x,y=y,width=width,height=32);return b
    button('⚙',open_settings,345,7,28);button('×',hide,383,7,28)
    button('‹',lambda:cycle(-1),22,201);minus=button('−',lambda:adjust(-1),75,201)
    step=label('1% / click',10,'#aab2bc');step.place(x=142,y=207)
    plus=button('+',lambda:adjust(1),316,201);button('›',lambda:cycle(1),372,201)
    drag={}
    def drag_start(event):drag.update(x=event.x_root-root.winfo_x(),y=event.y_root-root.winfo_y());service.activity()
    def drag_move(event):user32.SetWindowPos(hwnd,None,event.x_root-drag['x'],event.y_root-drag['y'],0,0,0x0001|0x0004|0x0010)
    for widget in (group,status,title):
        widget.configure(cursor='fleur');widget.bind('<Button-1>',drag_start);widget.bind('<B1-Motion>',drag_move)
    icon=pystray.Icon('SimPro Quick Control',Image.open(assets/'icon.png'),'SimPro Quick Control',pystray.Menu(
        pystray.MenuItem('Show adjustment popup',lambda *_:service.activity(),default=True),
        pystray.MenuItem('Open settings',lambda *_:open_settings()),
        pystray.MenuItem('Pause controls',lambda *_:background(lambda:service.enable(False))),
        pystray.MenuItem('Quit',lambda *_:quit_app())))
    threading.Thread(target=icon.run,daemon=True).start()
    root.update_idletasks();hwnd=user32.GetParent(root.winfo_id()) or root.winfo_id()
    user32.SetWindowLongPtrW(hwnd,-20,user32.GetWindowLongPtrW(hwnd,-20)|0x08000000)
    # Map Tk's child surface once; showing only its withdrawn native frame is blank.
    root.deiconify();root.update_idletasks();user32.ShowWindow(hwnd,0)
    def tick():
        if service.stop.is_set():root.destroy();return
        visible,stamp=service.menu_status();visible=visible and native['manual_hide_at']!=stamp
        if visible:
            state=service.state();key=state['config']['selected'];setting=next((s for s in state['settings'] if s['key']==key),None)
            signature=(key,state['values'].get(key),state['connected'],state['enabled'],state['multiplier'],state['config']['steps'].get(key),state.get('max_torque'))
            if signature!=native['signature']:
                native['signature']=signature
                status.configure(text='LIVE' if state['enabled'] else 'PAUSED' if state['connected'] else 'OFFLINE',fg='#8bd6b0' if state['enabled'] else '#aab2bc')
                if setting and state['connected']:
                    number=state['values'][key];choices=setting['choices']
                    group.configure(text=setting['group'].upper());title.configure(text=setting['label'])
                    value.configure(text=choices[number] if choices else f'{number}{setting["unit"]}')
                    secondary.configure(text=f'{number*state["max_torque"]/100:.2f} Nm · base output limit' if key=='total_force' else 'Live SimPro value')
                    multiplier=state['multiplier'];increment=state['config']['steps'].get(key,setting['step'])*multiplier
                    step.configure(text='Select' if choices else f'{increment}{setting["unit"]} / click'+(f' · ×{multiplier}' if multiplier>1 else ''))
                    meter.coords(fill,0,0,386*max(0,min(1,(number-setting['min'])/(setting['max']-setting['min']))),3)
                elif not state['connected']:
                    value.configure(text='—');secondary.configure(text='SimPro unavailable · open settings for details')
                minus.configure(state='normal' if state['enabled'] else 'disabled');plus.configure(state='normal' if state['enabled'] else 'disabled')
        if visible!=native['visible']:
            before=user32.GetForegroundWindow();user32.ShowWindow(hwnd,4 if visible else 0)
            if visible:user32.SetWindowPos(hwnd,ctypes.c_void_p(-1),0,0,0,0,0x0001|0x0002|0x0010)
            logging.info('Popup visible=%s focus_preserved=%s',bool(user32.IsWindowVisible(hwnd)),before==user32.GetForegroundWindow())
            native['visible']=visible
        root.after(100,tick)
    root.after(0,tick)
    try:root.mainloop()
    finally:service.stop.set();service.wake.set();icon.stop()
