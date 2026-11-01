import copy
import json
import math
import threading
import time
from collections import deque
from pathlib import Path
from core import SETTINGS,BY_KEY,Bindings,Visibility

SHARED={'increase','decrease','next','previous','show'}

def valid_action(action):
    return action in SHARED or any(action==k+':'+d for k in BY_KEY for d in ('increase','decrease'))

class ControlService:
    def __init__(self,client,config_path,clock=None):
        self.client=client; self.path=Path(config_path);self.clock=clock or time.monotonic
        self.lock=threading.RLock();self.operation=threading.RLock();self.stop=threading.Event()
        self.wake=threading.Event();self.saved_config=None
        self.config={'hide_after':5,'mode':'both','selected':'total_force','steps':{},'bindings':{},'acceleration':False,'auto_enable':False,
                     'cycle':[s['key'] for s in SETTINGS if s['group'] in ('Basic','Mechanical','Other effects')]}
        self.bindings=Bindings();self.visibility=Visibility(5,self.clock());self.enabled=False
        self.snapshot={'connected':False,'values':{},'settings':[]};self.error='Connecting to SimPro…'
        self.learning=None;self.learn_until=0;self.queue=deque(maxlen=64);self.devices=[];self.last_input='';self.input_error=''
        self.burst=None;self.burst_count=0;self.burst_at=-1;self.multiplier=1
        self.startup_enabled=False;self.manual_pause=False;self.write_fault=False;self.auto_pending=True
        self.quiet_startup=False
        if self.path.exists():
            try:
                loaded=json.loads(self.path.read_text('utf-8'))
                self._validate(loaded)
                self.config.update(loaded);self.bindings.items=copy.deepcopy(self.config['bindings'])
                self.visibility.timeout=self.config['hide_after']
            except Exception: self.error='Saved configuration could not be read; defaults loaded.'
    def _validate(self,patch):
        if not isinstance(patch,dict) or set(patch)-set(self.config): raise ValueError('Unknown configuration option')
        if 'acceleration' in patch and type(patch['acceleration']) is not bool:raise ValueError('Acceleration must be on or off')
        if 'auto_enable' in patch and type(patch['auto_enable']) is not bool:raise ValueError('Auto-enable must be on or off')
        if 'hide_after' in patch:
            n=patch['hide_after']
            if not isinstance(n,(int,float)) or not math.isfinite(n) or n<0 or n>600: raise ValueError('Hide delay must be 0–600 seconds')
        if 'mode' in patch and patch['mode'] not in ('shared','dedicated','both'): raise ValueError('Invalid control mode')
        if 'selected' in patch and patch['selected'] not in BY_KEY: raise ValueError('Unknown setting')
        if 'steps' in patch:
            if not isinstance(patch['steps'],dict): raise ValueError('Invalid steps')
            for k,n in patch['steps'].items():
                if k not in BY_KEY or type(n) is not int or not 1<=n<=100: raise ValueError('Step must be 1–100')
        if 'cycle' in patch and (not isinstance(patch['cycle'],list) or not patch['cycle'] or any(k not in BY_KEY for k in patch['cycle'])):
            raise ValueError('Choose at least one cycle setting')
        if 'bindings' in patch:
            if not isinstance(patch['bindings'],dict): raise ValueError('Invalid bindings')
            seen=set()
            for action,b in patch['bindings'].items():
                if not valid_action(action) or not isinstance(b,dict) or set(b)!={'device','button'}: raise ValueError('Invalid binding')
                if not isinstance(b['device'],str) or not b['device'] or type(b['button']) is not int or not 0<=b['button']<=2048: raise ValueError('Invalid button')
                ident=(b['device'],b['button'])
                if ident in seen: raise ValueError('One button can only have one action')
                seen.add(ident)
    def _save(self):
        encoded=json.dumps(self.config,indent=2)
        if encoded==self.saved_config:return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(encoded,'utf-8');tmp.replace(self.path)
        self.saved_config=encoded
    def _reset_burst(self):
        self.burst=None;self.burst_count=0;self.multiplier=1
    def update_config(self,patch):
        with self.lock:
            self._validate(patch)
            self._reset_burst()
            if patch.get('auto_enable'):self.auto_pending=True;self.manual_pause=False
            self.config.update(copy.deepcopy(patch));self.bindings.items=copy.deepcopy(self.config['bindings'])
            self.visibility.timeout=self.config['hide_after'];self.visibility.activity(self.clock());self._save()
    def state(self):
        with self.lock:
            if self.learning and self.clock()>self.learn_until: self.learning=None
            return copy.deepcopy({**self.snapshot,'config':self.config,'enabled':self.enabled,'error':self.error,
                'learning':self.learning,'devices':self.devices,'last_input':self.last_input,'input_error':self.input_error,'startup_enabled':self.startup_enabled,
                'menu_visible':self.visibility.visible(self.clock()),'pending':len(self.queue),
                'multiplier':self.multiplier if self.clock()-self.burst_at<=.25 else 1})
    def activity(self):
        with self.lock:self.visibility.activity(self.clock())
    def menu_status(self):
        with self.lock:return self.visibility.visible(self.clock()),self.visibility.last_activity
    def _failed(self,exc,latch=True):
        with self.lock:
            wake=self.snapshot['connected'] or self.error!=str(exc)
            self.error=str(exc);self.snapshot['connected']=False;self.enabled=False;self.queue.clear()
            self._reset_burst()
            if latch:self.write_fault=True
            if wake and not self.quiet_startup:self.visibility.activity(self.clock())
    def refresh(self):
        with self.operation:
            try:
                state=self.client.snapshot()
                with self.lock:
                    newly_connected=not self.snapshot['connected']
                    self.snapshot=state;self.error=''
                    self.quiet_startup=False
                    if self.config['auto_enable'] and (newly_connected or self.auto_pending) and not self.manual_pause and not self.write_fault and not self.input_error:
                        self.enabled=True;self.queue.clear();self._reset_burst()
                    self.auto_pending=False
                    if self.config['selected'] not in state['values']: self.config['selected']='total_force'
            except Exception as exc:self._failed(exc,latch=False)
    def enable(self,enabled):
        if type(enabled) is not bool:raise ValueError('Invalid enabled state')
        with self.operation:
            if enabled:self.refresh()
            with self.lock:
                if enabled and not self.snapshot['connected']:raise ValueError(self.error)
                self.enabled=enabled;self.queue.clear();self.visibility.activity(self.clock())
                self.manual_pause=not enabled
                if enabled:self.write_fault=False
                self._reset_burst()
    def learn(self,action):
        with self.lock:
            if action is not None and not valid_action(action):raise ValueError('Unknown action')
            self.learning=action;self.learn_until=self.clock()+20;self.queue.clear()
            self._reset_burst()
    def button(self,device,button):
        with self.lock:
            self.last_input=f'{device.split("|")[-1]} · button {button+1}'
            if self.learning and self.clock()<=self.learn_until:
                self.bindings.assign(self.learning,device,button);self.config['bindings']=copy.deepcopy(self.bindings.items)
                self.learning=None;self._save();return
            self.learning=None
            action=self.bindings.resolve(device,button)
            if not action:return
            self.visibility.activity(self.clock())
            if action=='show':self._reset_burst();return
            if action in ('next','previous'):
                self._reset_burst()
                if self.config['mode']=='dedicated':return
                keys=[k for k in self.config['cycle'] if k in self.snapshot['values']]
                if not keys:return
                index=keys.index(self.config['selected']) if self.config['selected'] in keys else -1
                self.config['selected']=keys[(index+(1 if action=='next' else -1))%len(keys)];self._save();return
            if not self.enabled or not self.snapshot['connected']:return
            if ':' in action:
                if self.config['mode']=='shared':return
                key,direction=action.split(':')
                self.config['selected']=key
            else:
                if self.config['mode']=='dedicated':return
                key=self.config['selected'];direction=action
            if key not in self.snapshot['values']:return
            now=self.clock();preset=self.snapshot['preset_id'];burst=(device,key,direction,preset)
            self.burst_count=self.burst_count+1 if burst==self.burst and 0<=now-self.burst_at<=.16 else 1
            self.burst=burst;self.burst_at=now
            self.multiplier=(10 if self.burst_count>=16 else 5 if self.burst_count>=8 else 2 if self.burst_count>=4 else 1) if self.config['acceleration'] and not BY_KEY[key]['choices'] else 1
            self.queue.append((now,key,self.multiplier*(1 if direction=='increase' else -1),preset))
            self.wake.set()
    def adjust(self,key,direction):
        if key not in BY_KEY or type(direction) is not int or direction not in (-1,1):raise ValueError('Invalid adjustment')
        with self.operation:
            with self.lock:
                if not self.enabled:raise ValueError('Enable controls before adjusting')
                step=self.config['steps'].get(key,BY_KEY[key]['step']);preset=self.snapshot.get('preset_id')
                self.config['selected']=key
            try:
                state=self.client.adjust(key,direction,step,expected_preset=preset)
                with self.lock:
                    self.snapshot=state;self.error='';self.visibility.activity(self.clock());self._save()
            except Exception as exc:self._failed(exc);raise
    def process_next(self):
        with self.operation:
            with self.lock:
                while self.queue and self.clock()-self.queue[0][0]>.75:self.queue.popleft()
                if not self.queue or not self.enabled:return
                stamp,key,delta,preset=self.queue.popleft()
                # Opposite ticks must remain ordered, especially at range limits.
                while self.queue and self.queue[0][1]==key and self.queue[0][3]==preset and self.queue[0][2]*delta>0:
                    _,_,extra,_=self.queue.popleft();delta+=extra
                step=self.config['steps'].get(key,BY_KEY[key]['step'])
            if not delta:return
            try:
                state=self.client.adjust(key,delta,step,expected_preset=preset)
                with self.lock:
                    self.snapshot=state;self.error='';self.visibility.activity(self.clock());self._save()
            except Exception as exc:self._failed(exc)
    def run(self):
        last_poll=0
        while not self.stop.is_set():
            self.wake.clear()
            self.process_next()
            interval=1 if self.enabled else 2
            if self.clock()-last_poll>=interval:
                self.refresh();last_poll=self.clock()
            with self.lock:pending=bool(self.queue)
            if not pending:self.wake.wait(max(.01,interval-(self.clock()-last_poll)))
