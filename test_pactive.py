import copy
import pytest
from core import adjusted_config
from simpro import SimproError
from pactive import ControlClient


class Rig(ControlClient):
    def __init__(self):
        super().__init__(confirm_timeout=.12)
        self.devices=[
            dict(device_uuid='BASE',product_uuid='00000000010B0000',product_type='base',product_name='Alpha EVO Ultra'),
            dict(device_uuid='PEDAL',product_uuid='0000000003050000',product_type='pedal',product_name='P-Active',param={'active_pedal_select_id':2}),
        ]
        self.pedal=dict(is_damping=True,damp_pressed=39,damp_released=69,is_friction=False,friction_strength=50,rev_friction_strength=50,front_stop_level=1,back_stop_level=1,future_field={'keep':7})
        self.preset='456';self.writes=[];self.accept=True
        self.curve={'paddles':[{'axis_paddle':{'y_max':65.4,'y_min':0,'x_min':5,'x_max':75,'calibrations':[{'x':0,'y':0},{'x':100,'y':100}]}}],'future':12}

    def call(self,method,body=None):
        body=body or {}
        if method=='get_device_list':return copy.deepcopy(self.devices)
        if method=='app_get_info':return {'app_version':'V3.2.5.13819-5dd62489'}
        base=body.get('device_uuid')=='BASE'
        if method=='preset_get_selected_dev_config':return {'preset_uuid':'123' if base else self.preset}
        if method=='device_base_get_status':return {'device_uuid':'BASE','max_torque':28}
        if method=='preset_get_dev_config':
            return {'preset_name':'Test','servos':{'1':{'total_force':90}},'config':{},'light_groups':{}} if base else {'preset_name':'Pedal test','pedals':{str(n):copy.deepcopy(self.pedal) for n in (1,2,3)},'paddle_groups':{str(n):copy.deepcopy(self.curve) for n in (1,2,3)}}
        if method=='preset_set_dev_config':
            self.writes.append(copy.deepcopy(body))
            if self.accept:
                if body['part_type']=='paddle_groups':self.curve=copy.deepcopy(body['config'])
                else:self.pedal=copy.deepcopy(body['config'])
            return None
        raise AssertionError(method)


def test_base_and_only_connected_pedal_role_share_settings():
    rig=Rig();s=rig.snapshot()
    assert s['values']['total_force']==90
    assert s['values']['pactive_2_damp_pressed']==39
    assert len([k for k in s['values'] if k.startswith('pactive_')])==9
    assert not any(k.startswith('pactive_1_') for k in s['values'])


def test_pedal_works_without_wheelbase():
    rig=Rig();rig.devices.pop(0);s=rig.snapshot()
    assert s['connected'] and s['max_torque']==0
    assert 'total_force' not in s['values']
    assert s['device']=='P-Active'


def test_pedal_write_targets_its_preset_and_preserves_other_fields():
    rig=Rig();s=rig.snapshot();key='pactive_2_damp_pressed';before=copy.deepcopy(rig.pedal)
    out=rig.adjust(key,-1,expected_preset=s['setting_presets'][key])
    assert out['values'][key]==38 and out['values']['total_force']==90
    assert rig.writes==[{'device_uuid':'PEDAL','product_uuid':'0000000003050000','preset_uuid':'456','part_type':'pedals','part_id':2,'config':{**before,'damp_pressed':38}}]


@pytest.mark.parametrize('change',['preset','role','device','disconnect'])
def test_queued_pedal_write_rejects_changed_target(change):
    rig=Rig();key='pactive_2_damp_pressed';token=rig.snapshot()['setting_presets'][key]
    if change=='preset':rig.preset='789'
    elif change=='role':rig.devices[1]['param']['active_pedal_select_id']=3
    elif change=='device':rig.devices[1]['device_uuid']='OTHER'
    else:rig.devices.pop()
    with pytest.raises((SimproError,ValueError)):rig.adjust(key,-1,expected_preset=token)
    assert not rig.writes


def test_pedal_timeout_is_not_retried():
    rig=Rig();rig.accept=False;key='pactive_2_damp_pressed'
    with pytest.raises(SimproError):rig.adjust(key,-1)
    assert len(rig.writes)==1


def test_pedal_bool_and_clamp_preserve_siblings():
    before={'is_damping':True,'damp_pressed':99,'future':12}
    assert adjusted_config(before,'pactive_2_is_damping',-1)=={**before,'is_damping':False}
    assert adjusted_config(before,'pactive_2_damp_pressed',10)=={**before,'damp_pressed':100}


def test_missing_pedal_field_is_omitted_and_cannot_be_written():
    rig=Rig();del rig.pedal['damp_pressed']
    assert 'pactive_2_damp_pressed' not in rig.snapshot()['values']
    with pytest.raises((SimproError,ValueError)):rig.adjust('pactive_2_damp_pressed',1)
    assert not rig.writes


def test_unknown_role_and_duplicate_pedals_are_not_guessed():
    rig=Rig();rig.devices[1]['param']['active_pedal_select_id']=9
    assert not any(k.startswith('pactive_') for k in rig.snapshot()['values'])
    rig.devices[1]['param']['active_pedal_select_id']=2
    rig.devices.append({**rig.devices[1],'device_uuid':'OTHER'})
    assert not any(k.startswith('pactive_') for k in rig.snapshot()['values'])


def test_service_routes_button_and_browser_adjustments_to_pedal(tmp_path):
    from service import ControlService
    rig=Rig();svc=ControlService(rig,tmp_path/'config.json');svc.enable(True)
    key='pactive_2_damp_pressed'
    svc.learn(key+':decrease');svc.button('wheel',4);svc.button('wheel',4);svc.process_next()
    assert rig.pedal['damp_pressed']==38
    svc.adjust(key,1)
    assert rig.pedal['damp_pressed']==39


def test_pedal_only_refresh_selects_available_value_and_cycle(tmp_path):
    from service import ControlService
    rig=Rig();rig.devices.pop(0);svc=ControlService(rig,tmp_path/'config.json')
    svc.config['cycle']=['total_force'];svc.refresh()
    s=svc.state()
    assert s['config']['selected'] in s['values']
    assert any(k in s['values'] for k in s['config']['cycle'])


@pytest.mark.parametrize('change',['disconnect','role','preset'])
def test_selected_target_change_pauses_before_shared_input_can_retarget(tmp_path,change):
    from service import ControlService
    rig=Rig();svc=ControlService(rig,tmp_path/'config.json');svc.enable(True)
    svc.update_config({'selected':'pactive_2_damp_pressed','auto_enable':True})
    if change=='disconnect':rig.devices.pop()
    elif change=='role':rig.devices[1]['param']['active_pedal_select_id']=3
    else:rig.preset='789'
    svc.refresh();svc.refresh()
    assert not svc.state()['enabled']
    svc._dispatch('increase','wheel');svc.process_next()
    assert not rig.writes
    svc.enable(True)
    assert svc.state()['enabled']


@pytest.mark.parametrize('bad',[True,101,-1,1.5,'40'])
def test_fresh_field_validation_cannot_be_bypassed(bad):
    class ChangingRig(Rig):
        reads=0
        def _pedal_read(self,devices):
            self.reads+=1
            if self.reads==2:self.pedal['damp_pressed']=bad
            return super()._pedal_read(devices)
    rig=ChangingRig()
    with pytest.raises((SimproError,ValueError)):rig.adjust('pactive_2_damp_pressed',1)
    assert not rig.writes


def test_force_preserves_fraction_and_entire_curve():
    rig=Rig();key='pactive_2_max_force';before=copy.deepcopy(rig.curve)
    assert rig.snapshot()['values'][key]==65.4
    out=rig.adjust(key,-1,.1)
    assert out['values'][key]==65.3
    before['paddles'][0]['axis_paddle']['y_max']=65.3
    assert rig.curve==before
    assert rig.writes[0]['part_type']=='paddle_groups'
    assert rig.writes[0]['part_id']==2
    assert rig.pedal['damp_pressed']==39


def test_force_clamps_above_minimum_and_below_180():
    rig=Rig();axis=rig.curve['paddles'][0]['axis_paddle'];axis.update(y_min=65,y_max=65.4)
    assert rig.adjust('pactive_2_max_force',-100)['values']['pactive_2_max_force']==65
    assert rig.adjust('pactive_2_max_force',100,100)['values']['pactive_2_max_force']==180


@pytest.mark.parametrize('bad',[None,True,float('nan'),181,-1,'65.4'])
def test_invalid_force_is_not_offered(bad):
    rig=Rig();rig.curve['paddles'][0]['axis_paddle']['y_max']=bad
    assert 'pactive_2_max_force' not in rig.snapshot()['values']
    with pytest.raises(SimproError):rig.adjust('pactive_2_max_force',1)
    assert not rig.writes


def test_force_requires_unambiguous_curve_and_valid_minimum():
    rig=Rig();rig.curve['paddles'].append(copy.deepcopy(rig.curve['paddles'][0]))
    assert 'pactive_2_max_force' not in rig.snapshot()['values']
    rig.curve['paddles'].pop();rig.curve['paddles'][0]['axis_paddle']['y_min']=70
    assert 'pactive_2_max_force' not in rig.snapshot()['values']


def test_force_step_configuration_and_service_route(tmp_path):
    from service import ControlService
    rig=Rig();svc=ControlService(rig,tmp_path/'config.json');key='pactive_2_max_force'
    svc.update_config({'steps':{key:.1}});svc.enable(True);svc.adjust(key,1)
    assert rig.curve['paddles'][0]['axis_paddle']['y_max']==65.5
    for steps in ({key:.01},{key:True},{key:.1000000001},{'pactive_2_damp_pressed':.1},{'total_force':1.000000001}):
        with pytest.raises(ValueError):svc.update_config({'steps':steps})
