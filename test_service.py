from pathlib import Path
import pytest
from service import ControlService

class Base:
    def __init__(self): self.force=50;self.offline=False;self.changes=[]
    def snapshot(self):
        if self.offline: raise RuntimeError('Disconnected')
        return {'connected':True,'preset_id':'123','device':'Alpha EVO Ultra','max_torque':28,'values':{'total_force':self.force,'mechanical_damper':8},'settings':[]}
    def adjust(self,key,delta,step=1,expected_preset=None):
        self.snapshot();self.changes.append((key,delta,step));self.force+=delta*step
        return self.snapshot()

def make(tmp_path):
    now=[0];base=Base();svc=ControlService(base,tmp_path/'config.json',clock=lambda:now[0]);svc.refresh()
    return svc,base,now

def test_learning_consumes_input_without_adjusting(tmp_path):
    svc,base,now=make(tmp_path);svc.enable(True);svc.learn('increase');svc.button('wheel',35);svc.process_next()
    assert base.changes==[]
    assert svc.state()['config']['bindings']['increase']=={'device':'wheel','button':35}
    svc.button('wheel',35);svc.process_next()
    assert base.force==51

def test_old_input_is_never_replayed(tmp_path):
    svc,base,now=make(tmp_path);svc.learn('increase');svc.button('wheel',1);svc.enable(True)
    svc.button('wheel',1);now[0]=3;svc.process_next()
    assert base.changes==[]

def test_disconnect_disables_and_discards_pending_inputs(tmp_path):
    svc,base,now=make(tmp_path);svc.learn('increase');svc.button('wheel',1);svc.enable(True)
    svc.button('wheel',1);base.offline=True;svc.refresh();base.offline=False;svc.refresh();svc.process_next()
    assert not svc.state()['enabled']
    assert not base.changes

def test_dedicated_binding_targets_its_setting(tmp_path):
    svc,base,now=make(tmp_path);svc.learn('mechanical_damper:decrease');svc.button('wheel',3);svc.enable(True)
    svc.button('wheel',3);svc.process_next()
    assert base.changes==[('mechanical_damper',-1,1)]

def test_saved_config_restores_and_timeout_can_be_disabled(tmp_path):
    svc,base,now=make(tmp_path);svc.update_config({'hide_after':10,'mode':'both'});svc.learn('next');svc.button('wheel',5)
    restored=ControlService(base,tmp_path/'config.json',clock=lambda:0)
    assert restored.state()['config']['hide_after']==10
    assert restored.state()['config']['bindings']['next']['button']==5
    restored.update_config({'hide_after':0})
    assert restored.state()['menu_visible']

@pytest.mark.parametrize('patch',[{'hide_after':-1},{'hide_after':float('nan')},{'mode':'invalid'},{'steps':{'total_force':0}}])
def test_invalid_configuration_does_not_persist(tmp_path,patch):
    svc,base,now=make(tmp_path)
    with pytest.raises(ValueError): svc.update_config(patch)

def test_offline_polling_does_not_keep_waking_popup(tmp_path):
    svc,base,now=make(tmp_path);base.offline=True;svc.refresh()
    now[0]=7;svc.refresh()
    assert not svc.state()['menu_visible']

def test_opposite_encoder_ticks_are_applied_in_order(tmp_path):
    svc,base,now=make(tmp_path)
    svc.learn('increase');svc.button('wheel',1);svc.learn('decrease');svc.button('wheel',2);svc.enable(True)
    svc.button('wheel',1);svc.button('wheel',2);svc.process_next();svc.process_next()
    assert base.changes==[('total_force',1,1),('total_force',-1,1)]

def test_dedicated_selection_is_persisted_after_change(tmp_path):
    svc,base,now=make(tmp_path);svc.learn('mechanical_damper:decrease');svc.button('wheel',3);svc.enable(True)
    svc.button('wheel',3);svc.process_next()
    again=ControlService(base,tmp_path/'config.json')
    assert again.state()['config']['selected']=='mechanical_damper'

def test_acceleration_ramps_and_resets_on_pause_and_reverse(tmp_path):
    svc,base,now=make(tmp_path);svc.update_config({'acceleration':True})
    svc.learn('increase');svc.button('wheel',1);svc.learn('decrease');svc.button('wheel',2);svc.enable(True)
    for i in range(16):
        now[0]=i*.05;svc.button('wheel',1);svc.process_next()
    assert [v[1] for v in base.changes]==[1,1,1,2,2,2,2,5,5,5,5,5,5,5,5,10]
    now[0]+=.05;svc.button('wheel',2);svc.process_next()
    assert base.changes[-1][1]==-1
    now[0]+=1;svc.button('wheel',1);svc.process_next()
    assert base.changes[-1][1]==1

def test_acceleration_off_and_slow_turning_keep_normal_step(tmp_path):
    svc,base,now=make(tmp_path);svc.learn('increase');svc.button('wheel',1);svc.enable(True)
    for i in range(20):
        now[0]=i*.01;svc.button('wheel',1);svc.process_next()
    assert all(x[1]==1 for x in base.changes)
    svc.update_config({'acceleration':True})
    for i in range(20):
        now[0]+=1;svc.button('wheel',1);svc.process_next()
    assert all(x[1]==1 for x in base.changes)

def test_acceleration_never_multiplies_choice_settings(tmp_path):
    svc,base,now=make(tmp_path);base.snapshot=lambda:{'connected':True,'preset_id':'123','values':{'reverse':0},'settings':[]}
    svc.refresh();svc.update_config({'acceleration':True,'selected':'reverse'})
    svc.learn('increase');svc.button('wheel',1);svc.enable(True)
    for i in range(20):
        now[0]=i*.02;svc.button('wheel',1);svc.process_next()
    assert all(x[1]==1 for x in base.changes)

def test_queued_completion_preserves_new_selection(tmp_path):
    svc,base,now=make(tmp_path);svc.learn('increase');svc.button('wheel',1);svc.enable(True)
    svc.button('wheel',1);svc.update_config({'selected':'mechanical_damper'});svc.process_next()
    assert svc.state()['config']['selected']=='mechanical_damper'

def test_opt_in_auto_enable_on_connect_and_reconnect(tmp_path):
    svc,base,now=make(tmp_path);svc.update_config({'auto_enable':True});svc.refresh()
    assert svc.enabled
    base.offline=True;svc.refresh();assert not svc.enabled
    base.offline=False;svc.refresh();assert svc.enabled

def test_auto_enable_respects_manual_pause_and_write_fault(tmp_path):
    svc,base,now=make(tmp_path);svc.update_config({'auto_enable':True});svc.refresh();svc.enable(False)
    base.offline=True;svc.refresh();base.offline=False;svc.refresh();assert not svc.enabled
    svc.enable(True);svc._failed(RuntimeError('Unconfirmed write'))
    svc.refresh();assert not svc.enabled
    svc.enable(True);assert svc.enabled

def test_auto_enable_is_off_by_default(tmp_path):
    svc,base,now=make(tmp_path);svc.refresh();assert not svc.enabled

def test_quiet_startup_stays_hidden_when_simpro_is_not_running(tmp_path):
    svc,base,now=make(tmp_path);svc.quiet_startup=True;svc.visibility.last_activity=-601
    base.offline=True;svc.refresh();assert not svc.state()['menu_visible']
    base.offline=False;svc.refresh();assert not svc.state()['menu_visible']
