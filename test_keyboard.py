import pytest
from test_service import make
from keyboard_reader import validate_shortcut,shortcut_label,HotkeyRegistry

def test_keyboard_and_usb_bindings_coexist_and_persist(tmp_path):
    svc,base,now=make(tmp_path);svc.learn('increase');svc.button('wheel',3)
    svc.update_config({'keyboard':{'increase':{'key':'KeyK','modifiers':3}}})
    svc.enable(True);svc.keyboard('increase',{'key':'KeyK','modifiers':3});svc.process_next()
    svc.button('wheel',3);svc.process_next()
    assert base.force==52
    assert svc.state()['config']['bindings']['increase']['button']==3

def test_keyboard_respects_pause_and_learning(tmp_path):
    svc,base,now=make(tmp_path);chord={'key':'F9','modifiers':0}
    svc.update_config({'keyboard':{'increase':chord}})
    svc.keyboard('increase',chord);svc.process_next();assert base.force==50
    svc.enable(True);svc.learn('decrease');svc.keyboard('increase',chord);svc.process_next()
    assert base.force==50 and svc.learning=='decrease'

def test_keyboard_does_not_accelerate_and_rejects_stale_event(tmp_path):
    svc,base,now=make(tmp_path);chord={'key':'F9','modifiers':0}
    svc.update_config({'keyboard':{'increase':chord},'acceleration':True});svc.enable(True)
    for i in range(20):
        now[0]=i*.02;svc.keyboard('increase',chord);svc.process_next()
    assert base.force==70
    svc.update_config({'keyboard':{}});svc.keyboard('increase',chord);svc.process_next()
    assert base.force==70

def test_duplicate_keyboard_chords_are_rejected(tmp_path):
    svc,base,now=make(tmp_path);chord={'key':'F9','modifiers':0}
    with pytest.raises(ValueError):svc.update_config({'keyboard':{'increase':chord,'decrease':chord}})

@pytest.mark.parametrize('chord',[{'key':'KeyA','modifiers':0},{'key':'F12','modifiers':2},{'key':'F9','modifiers':8},{'key':'Bogus','modifiers':3},{'key':'F9','modifiers':True}])
def test_invalid_or_reserved_shortcuts_are_rejected(chord):
    with pytest.raises(ValueError):validate_shortcut(chord)

def test_chord_label():
    assert shortcut_label({'key':'ArrowUp','modifiers':7})=='Ctrl+Alt+Shift+Up'

def test_registration_conflict_and_rebind_release_old_hotkeys():
    calls=[]
    def register(ident,mods,vk):calls.append((ident,mods,vk));return vk!=0x79
    released=[];registry=HotkeyRegistry(register,released.append)
    first={'show':{'key':'F9','modifiers':0},'next':{'key':'F10','modifiers':0}}
    errors=registry.sync(first)
    assert 'next' in errors and 'show' not in errors
    assert calls[0][1]&0x4000
    old_id=calls[0][0];assert registry.actions[old_id][0]=='show'
    registry.sync({'previous':{'key':'F8','modifiers':2}})
    assert old_id in released and old_id not in registry.actions
    registry.close();assert not registry.actions
