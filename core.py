"""Pure control rules. Ranges verified against SimPro 3.2.4's EVO UI."""
import copy
import math

def setting(key, label, group, low, high, unit='', step=1, choices=None, part='servos', field=None):
    return dict(key=key,label=label,group=group,min=low,max=high,unit=unit,step=step,
                choices=choices,part=part,field=field or key)

SETTINGS = [
    setting('total_force','FFB strength','Basic',0,100,'%'),
    setting('filter_level','Filter level','Basic',0,20),
    setting('wheel_return_speed','Wheel rotation speed','Basic',0,100),
    setting('vehicle_suspension','FFB detail','Basic',0,20),
    setting('synthesis_filter_coe','Dynamic prediction level','Mechanical',0,10),
    setting('eps','Steering torque assist','Mechanical',0,100,'%'),
    setting('mechanical_damper','Mechanical damper','Mechanical',0,100,'%'),
    setting('mechanical_friction','Mechanical friction','Mechanical',0,100,'%'),
    setting('mechanical_inertia','Mechanical inertia','Mechanical',0,100,'%'),
    setting('torque_rate','Slew rate control','Mechanical',0,100,'%'),
    setting('mechanical_spring','Mechanical spring','Other effects',0,100,'%'),
    setting('central_damper','Center damper','Other effects',0,100,'%'),
    setting('game_inertia','Game inertia','Other effects',0,200,'%'),
    setting('game_spring','Game spring','Other effects',0,200,'%'),
    setting('game_damper','Game damper','Other effects',0,200,'%'),
    setting('game_friction','Game friction','Other effects',0,200,'%'),
    setting('max_wheel_angle','Steering angle','Steering',45,2520,'°',10),
    setting('wheel_angle_limit','Hard lock angle','Steering',45,2520,'°',10),
    setting('soft_lock_strength','Limit strength','Steering',0,2,choices=['Soft','Normal','Firm']),
    setting('reverse','Reverse FFB','Steering',0,1,choices=['Off','On'],field='total_force'),
    setting('brightness','Ring light brightness','Lights',0,100,'%',part='global'),
    setting('ring_on','Ring light','Lights',0,1,choices=['Off','On'],part='light_groups',field='is_on'),
]
BASE_SETTINGS = list(SETTINGS)
PEDAL_SETTINGS = []
for part_id, role in ((1,'Clutch'),(2,'Brake'),(3,'Throttle')):
    for field,label,maximum,choices in (
        ('is_damping','Damping',1,['Off','On']),
        ('damp_pressed','Press damping',100,None),
        ('damp_released','Release damping',100,None),
        ('is_friction','Friction',1,['Off','On']),
        ('friction_strength','Press friction',100,None),
        ('rev_friction_strength','Release friction',100,None),
        ('front_stop_level','Front stop',2,['Soft','Normal','Firm']),
        ('back_stop_level','Back stop',2,['Soft','Normal','Firm']),
    ):
        item=setting(f'pactive_{part_id}_{field}',label,'P-Active '+role,0,maximum,
                     '%' if maximum==100 else '',choices=choices,part='pedals',field=field)
        item.update(device='pactive',part_id=part_id,boolean=field.startswith('is_'))
        PEDAL_SETTINGS.append(item)
    item=setting(f'pactive_{part_id}_max_force','Maximum force','P-Active '+role,0,180,'kg',part='paddle_groups',field='y_max')
    item.update(device='pactive',part_id=part_id,boolean=False,precision=1,step_min=.1,
                path=['paddles',0,'axis_paddle','y_max'])
    PEDAL_SETTINGS.append(item)
SETTINGS += PEDAL_SETTINGS
BY_KEY = {s['key']:s for s in SETTINGS}

def field_value(current, setting):
    value=current
    for key in setting.get('path',[setting['field']]):value=value[key]
    return value

def valid_step(key, step):
    if key not in BY_KEY or type(step) not in (int,float) or not math.isfinite(step):return False
    minimum=BY_KEY[key].get('step_min',1)
    return minimum<=step<=100 and step==round(step,BY_KEY[key].get('precision',0))

def value_of(current, key):
    s=BY_KEY[key]
    value=field_value(current,s)
    if key=='reverse': return int(math.copysign(1,value)<0)
    if key=='total_force': return abs(value)
    return round(value,s['precision']) if s.get('precision') else int(value)

def adjusted_config(current, key, delta, step=1):
    if key not in BY_KEY or not isinstance(delta,(int,float)) or not math.isfinite(delta):
        raise ValueError('Unknown setting or invalid change')
    if not valid_step(key,step):raise ValueError('Invalid step for this setting')
    s=BY_KEY[key]
    try:field_value(current,s)
    except (KeyError,IndexError,TypeError):raise ValueError('Setting is unavailable')
    maximum=s['max']
    minimum=s['min']
    if s.get('path'):minimum=max(minimum,math.ceil(current['paddles'][0]['axis_paddle']['y_min']*10-1e-8)/10)
    if key=='wheel_angle_limit': maximum=min(maximum,current.get('max_wheel_angle',maximum))
    value=max(minimum,min(maximum,value_of(current,key)+delta*step))
    value=round(value,s['precision']) if s.get('precision') else int(value)
    out=copy.deepcopy(current)
    if s.get('path'):
        target=out
        for part in s['path'][:-1]:target=target[part]
        target[s['path'][-1]]=value
    elif key=='reverse': out['total_force']=math.copysign(abs(current['total_force']),-1 if value else 1)
    elif key=='total_force': out['total_force']=math.copysign(value,current['total_force'])
    elif key=='max_wheel_angle': out.update(max_wheel_angle=value,wheel_angle_limit=value)
    elif key=='ring_on': out['is_on']=bool(value)
    else: out[s['field']]=bool(value) if s.get('boolean') else value
    return out

class Bindings:
    def __init__(self):
        self.items = {}
    def assign(self, action, device, button):
        if not isinstance(device,str) or not device or not isinstance(button,int) or button<0 or button>2048:
            raise ValueError('Invalid joystick input')
        self.items={a:b for a,b in self.items.items() if a!=action and b!={'device':device,'button':button}}
        self.items[action]={'device':device,'button':button}
    def resolve(self, device, button):
        return next((a for a,b in self.items.items() if b=={'device':device,'button':button}),None)

class ButtonEdges:
    def __init__(self): self.states={}
    def update(self, device, pressed):
        previous=self.states.get(device)
        self.states[device]=set(pressed)
        return set() if previous is None else set(pressed)-previous
    def remove(self, device):
        self.states.pop(device,None)

class Visibility:
    def __init__(self, timeout=5, now=0):
        self.timeout=timeout
        self.last_activity=now
    def activity(self, now):
        self.last_activity=now
    def visible(self, now, configuring=False):
        return configuring or self.timeout==0 or now-self.last_activity<self.timeout
