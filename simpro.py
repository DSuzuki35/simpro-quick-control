import copy
import json
import logging
import threading
import time
from http.client import HTTPConnection
from urllib.parse import urlsplit
import re
from core import SETTINGS,BY_KEY,value_of,adjusted_config

class SimproError(Exception): pass

class SimproClient:
    def __init__(self, base_url='http://127.0.0.1:56791/simpro/api/v3', confirm_timeout=2):
        self.base_url=base_url
        self.endpoint=urlsplit(base_url)
        if self.endpoint.scheme!='http' or self.endpoint.hostname not in ('127.0.0.1','localhost'):
            raise ValueError('SimPro must use local HTTP')
        self.confirm_timeout=confirm_timeout
        self.lock=threading.RLock()
        self.device_id=None
        self.zero_reverse={}
        self.last_failure=None
        self.compatibility={'tested':'3.2.4.13771','detected':'Unknown','experimental':True}
        self.version_checked_at=-60
    def call(self,method,body=None):
        try:
            connection=HTTPConnection(self.endpoint.hostname,self.endpoint.port,timeout=2)
            try:
                connection.request('POST',self.endpoint.path+'/'+method,body=json.dumps(body or {}).encode(),headers={'Content-Type':'application/json'})
                response=connection.getresponse()
                if response.status!=200:raise SimproError(f'SimPro returned HTTP {response.status}')
                data=json.loads(response.read())
            finally:connection.close()
            if data.get('status')!=200: raise SimproError(data.get('message') or 'SimPro rejected the request')
            return data.get('result')
        except SimproError: raise
        except Exception as exc:
            detail=f'{type(exc).__name__}: {exc}'
            if detail!=self.last_failure:
                logging.exception('SimPro request failed: %s',method);self.last_failure=detail
            raise SimproError('Cannot reach SimPro. Keep SimPro Manager open. ('+detail+')') from exc
    def _read(self):
        devices=self.call('get_device_list')
        bases=[d for d in devices if d.get('product_type')=='base']
        if self.device_id: bases=[d for d in bases if d.get('device_uuid')==self.device_id]
        if len(bases)!=1: raise SimproError('Connect the selected wheelbase; exactly one base is required at first launch.')
        device=bases[0]
        if device.get('product_uuid')!='00000000010B0000': raise SimproError('This build is verified for the Alpha EVO Ultra.')
        self.device_id=device['device_uuid']
        if time.monotonic()-self.version_checked_at>=60:
            self.version_checked_at=time.monotonic()
            try:
                info=self.call('app_get_info') or {}
                detected=str(info.get('app_version','Unknown'))
                version=re.search(r'\d+\.\d+\.\d+\.\d+',detected)
                self.compatibility={'tested':'3.2.4.13771','detected':detected,'experimental':not version or version.group()!='3.2.4.13771'}
            except SimproError:
                self.compatibility={'tested':'3.2.4.13771','detected':'Unknown','experimental':True}
        identity={k:device[k] for k in ('device_uuid','product_uuid')}
        selected=self.call('preset_get_selected_dev_config',identity)
        preset_id=selected.get('preset_uuid')
        if not isinstance(preset_id,str) or not preset_id.isdigit(): raise SimproError('No active base preset')
        identity['preset_uuid']=preset_id
        config=self.call('preset_get_dev_config',identity)
        status=self.call('device_base_get_status',identity)
        if status.get('device_uuid')!=device['device_uuid'] or status.get('max_torque',0)<=0:
            raise SimproError('The wheelbase is unavailable')
        parts={'servos':config.get('servos',{}).get('1',{}),'global':config.get('config',{}),'light_groups':config.get('light_groups',{}).get('1',{})}
        if not isinstance(parts['servos'].get('total_force'),(int,float)): raise SimproError('SimPro returned an unfamiliar settings format')
        force=parts['servos']['total_force']
        if force:self.zero_reverse[preset_id]=force<0
        elif self.zero_reverse.get(preset_id):parts['servos']['total_force']=-0.0
        values={s['key']:value_of(parts[s['part']],s['key']) for s in SETTINGS if s['field'] in parts[s['part']]}
        state=dict(connected=True,device=device['product_name'],device_id=device['device_uuid'],preset_id=preset_id,
                   preset_name=config.get('preset_name',''),max_torque=status['max_torque'],values=values,
                   settings=[s for s in SETTINGS if s['key'] in values],compatibility=self.compatibility)
        return state,identity,parts
    def snapshot(self):
        with self.lock: return self._read()[0]
    def adjust(self,key,delta,step=1,expected_preset=None):
        if key not in BY_KEY: raise ValueError('Unknown setting')
        with self.lock:
            state,identity,parts=self._read()
            if expected_preset is not None and state['preset_id']!=expected_preset:
                raise SimproError('The active preset changed. Enable controls again.')
            setting=BY_KEY[key]
            current=parts[setting['part']]
            config=adjusted_config(current,key,delta,step)
            if key in ('reverse','total_force') and config['total_force']==0:
                self.zero_reverse[state['preset_id']]=bool(value_of(config,'reverse'))
                state['values']['reverse']=value_of(config,'reverse')
            if config==current: return state
            if 'total_force' in config:config['total_force']=int(config['total_force'])
            self.call('preset_set_dev_config',{**identity,'part_type':setting['part'],
                'part_id':0 if setting['part']=='global' else 1,'config':config})
            expected=value_of(config,key)
            deadline=time.monotonic()+self.confirm_timeout
            while time.monotonic()<deadline:
                time.sleep(.05)
                confirmed,_,_=self._read()
                if confirmed['preset_id']!=state['preset_id']: raise SimproError('Preset changed during adjustment; controls paused.')
                if confirmed['values'].get(key)==expected: return confirmed
            raise SimproError('SimPro did not confirm the change. Controls paused; check SimPro before re-enabling.')
