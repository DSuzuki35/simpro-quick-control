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
BY_KEY = {s['key']:s for s in SETTINGS}

def value_of(current, key):
    s=BY_KEY[key]
    value=current[s['field']]
    if key=='reverse': return int(math.copysign(1,value)<0)
    if key=='total_force': return abs(value)
    return int(value)

def adjusted_config(current, key, delta, step=1):
    if key not in BY_KEY or not isinstance(delta,(int,float)) or not math.isfinite(delta):
        raise ValueError('Unknown setting or invalid change')
    if not isinstance(step,(int,float)) or not math.isfinite(step) or step<1 or step>100 or int(step)!=step:
        raise ValueError('Step must be a whole number from 1 to 100')
    s=BY_KEY[key]
    if s['field'] not in current: raise ValueError('Setting is unavailable')
    maximum=s['max']
    if key=='wheel_angle_limit': maximum=min(maximum,current.get('max_wheel_angle',maximum))
    value=int(max(s['min'],min(maximum,value_of(current,key)+delta*step)))
    out=copy.deepcopy(current)
    if key=='reverse': out['total_force']=math.copysign(abs(current['total_force']),-1 if value else 1)
    elif key=='total_force': out['total_force']=math.copysign(value,current['total_force'])
    elif key=='max_wheel_angle': out.update(max_wheel_angle=value,wheel_angle_limit=value)
    elif key=='ring_on': out['is_on']=bool(value)
    else: out[s['field']]=value
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
