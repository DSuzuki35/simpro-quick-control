import copy
import pytest
from core import adjusted_config, Bindings, ButtonEdges, Visibility

def test_strength_clamps_and_preserves_other_fields():
    current = {'total_force': 99, 'mechanical_damper': 8, 'angle_values': [{'value': 900}]}
    original = copy.deepcopy(current)
    assert adjusted_config(current, 'total_force', 5)['total_force'] == 100
    assert adjusted_config(current, 'total_force', -200)['total_force'] == 0
    assert adjusted_config(current, 'total_force', -1)['mechanical_damper'] == 8
    assert current == original

def test_reversed_force_keeps_sign_when_adjusting_strength():
    assert adjusted_config({'total_force': -60}, 'total_force', 1)['total_force'] == -61
    assert adjusted_config({'total_force': -60}, 'reverse', -1)['total_force'] == 60
    assert adjusted_config({'total_force': 60}, 'reverse', 1)['total_force'] == -60

def test_reverse_direction_survives_zero_strength_in_control_rules():
    zero=adjusted_config({'total_force':-1},'total_force',-1)
    assert adjusted_config(zero,'total_force',1)['total_force']==-1

def test_steering_angle_updates_the_paired_hard_lock():
    out = adjusted_config({'max_wheel_angle': 900, 'wheel_angle_limit': 900}, 'max_wheel_angle', 1, 10)
    assert out == {'max_wheel_angle': 910, 'wheel_angle_limit': 910}

def test_independent_hard_lock_cannot_exceed_steering_angle():
    out = adjusted_config({'max_wheel_angle': 900, 'wheel_angle_limit': 895}, 'wheel_angle_limit', 1, 10)
    assert out['wheel_angle_limit'] == 900

def test_limits_are_specific_to_settings():
    assert adjusted_config({'filter_level': 19}, 'filter_level', 1, 5)['filter_level'] == 20
    assert adjusted_config({'game_damper': 190}, 'game_damper', 1, 20)['game_damper'] == 200
    assert adjusted_config({'soft_lock_strength': 2}, 'soft_lock_strength', 1)['soft_lock_strength'] == 2

@pytest.mark.parametrize('key,delta,step', [('firmware',1,1),('total_force',1,0),('total_force',float('nan'),1),('total_force',1,1000)])
def test_invalid_controls_are_rejected(key,delta,step):
    with pytest.raises(ValueError): adjusted_config({'total_force':100},key,delta,step)

def test_binding_reassignment_removes_conflicting_action():
    b=Bindings(); b.assign('increase','wheel',32); b.assign('decrease','wheel',32)
    assert b.resolve('wheel',32)=='decrease'
    assert 'increase' not in b.items

def test_button_connect_and_reconnect_do_not_fire_held_buttons():
    e=ButtonEdges()
    assert e.update('wheel',{3})==set()
    assert e.update('wheel',{3,4})=={4}
    assert e.update('wheel',{3,4})==set()
    e.remove('wheel')
    assert e.update('wheel',{4})==set()

def test_inactivity_uses_adjustment_time_and_configuration_keeps_visible():
    v=Visibility(5,0)
    assert v.visible(4.99)
    assert not v.visible(5)
    v.activity(10)
    assert v.visible(14.9)
    assert not v.visible(15)
    assert v.visible(50,configuring=True)
    assert Visibility(0,0).visible(10000)
