"""P-Active preset tuning. No factory movement or calibration commands."""
import math
import time
from core import PEDAL_SETTINGS,BY_KEY,value_of,adjusted_config
from simpro import SimproClient,SimproError

PRODUCT='0000000003050000'


class ControlClient(SimproClient):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.pedal_id=None

    def _pedal_read(self,devices):
        pedals=[d for d in devices if d.get('product_uuid')==PRODUCT]
        if len(pedals)!=1:raise SimproError('Connect exactly one P-Active controller.')
        device=pedals[0]
        if self.pedal_id and device['device_uuid']!=self.pedal_id:
            raise SimproError('The connected P-Active changed. Restart to select it.')
        part=(device.get('param') or {}).get('active_pedal_select_id')
        if type(part) is not int or part not in (1,2,3):raise SimproError('P-Active reports an unknown pedal role.')
        identity={k:device[k] for k in ('device_uuid','product_uuid')}
        selected=self.call('preset_get_selected_dev_config',identity)
        preset=selected.get('preset_uuid')
        if not isinstance(preset,str) or not preset.isdigit():raise SimproError('No active P-Active preset')
        identity['preset_uuid']=preset
        config=self.call('preset_get_dev_config',identity)
        current=config.get('pedals',{}).get(str(part),{})
        settings=[];values={}
        for setting in PEDAL_SETTINGS:
            if setting['part_id']!=part:continue
            raw=current.get(setting['field'])
            if setting['boolean']:
                valid=type(raw) is bool
            else:
                valid=type(raw) in (int,float) and math.isfinite(raw) and int(raw)==raw and setting['min']<=raw<=setting['max']
            if valid:settings.append(setting);values[setting['key']]=value_of(current,setting['key'])
        if not settings:raise SimproError('P-Active returned an unfamiliar settings format.')
        self.pedal_id=device['device_uuid'];self._check_version()
        state=dict(connected=True,device='P-Active',device_id=device['device_uuid'],preset_id=preset,
                   preset_name=config.get('preset_name',''),max_torque=0,settings=settings,values=values,compatibility=self.compatibility)
        return state,identity,current,part

    @staticmethod
    def _target(state,part=0):
        return f"{state['device_id']}:{state['preset_id']}:{part}"

    def snapshot(self):
        with self.lock:
            devices=self.call('get_device_list');states=[];warnings=[]
            if any(d.get('product_type')=='base' for d in devices):
                try:states.append((self._read(devices)[0],0))
                except SimproError as exc:warnings.append(str(exc))
            if any(d.get('product_uuid')==PRODUCT for d in devices):
                try:
                    state,_,_,part=self._pedal_read(devices);states.append((state,part))
                except SimproError as exc:warnings.append(str(exc))
            if not states:raise SimproError('; '.join(warnings) or 'Connect an Alpha EVO Ultra or P-Active and keep SimPro open.')
            result={**states[0][0],'values':{},'settings':[],'setting_presets':{},'setting_context':{},'device_warnings':warnings}
            result['device']=' + '.join(s['device'] for s,_ in states)
            for state,part in states:
                result['values'].update(state['values']);result['settings'].extend(state['settings'])
                for key in state['values']:
                    result['setting_presets'][key]=self._target(state,part)
                    result['setting_context'][key]={'device':state['device'],'preset_name':state['preset_name']}
            return result

    def adjust(self,key,delta,step=1,expected_preset=None):
        if key not in BY_KEY:raise ValueError('Unknown setting')
        with self.lock:
            state=self.snapshot()
            if key not in state['values']:raise SimproError('The selected setting or device is unavailable.')
            token=state['setting_presets'][key]
            if expected_preset is not None and token!=expected_preset:
                raise SimproError('Device, pedal role or preset changed. Enable controls again.')
            if BY_KEY[key].get('device')!='pactive':
                super().adjust(key,delta,step,expected_preset=state['preset_id'])
                return self.snapshot()
            latest,identity,current,part=self._pedal_read(self.call('get_device_list'))
            if self._target(latest,part)!=token:raise SimproError('P-Active target changed before adjustment.')
            if key not in latest['values']:raise SimproError('P-Active setting became unavailable or invalid before adjustment.')
            config=adjusted_config(current,key,delta,step)
            if config==current:return state
            self.call('preset_set_dev_config',{**identity,'part_type':'pedals','part_id':part,'config':config})
            expected=value_of(config,key);deadline=time.monotonic()+self.confirm_timeout
            while time.monotonic()<deadline:
                time.sleep(.05)
                confirmed=self.snapshot()
                if confirmed['setting_presets'].get(key)!=token:raise SimproError('P-Active target changed during adjustment; controls paused.')
                if confirmed['values'].get(key)==expected:return confirmed
            raise SimproError('SimPro did not confirm the P-Active change. Controls paused; check SimPro before re-enabling.')
