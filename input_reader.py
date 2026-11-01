"""SDL input remains active while the game owns keyboard focus."""
import os
os.environ['SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS']='1'
os.environ['SDL_JOYSTICK_HIDAPI']='0'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
import time
from core import ButtonEdges

def run_inputs(service):
    import pygame
    pygame.display.init();pygame.joystick.init()
    joysticks={};identities={};metadata={};edges=ButtonEdges();last_devices=0;watch_signature=None
    def identity(js):return js.get_guid()+'|'+js.get_name()
    def add(index):
        js=pygame.joystick.Joystick(index);instance=js.get_instance_id()
        joysticks[instance]=js;identities[instance]=identity(js)
        metadata[instance]=dict(id=identity(js),name=js.get_name(),buttons=js.get_numbuttons(),index=index)
        pressed={i for i in range(js.get_numbuttons()) if js.get_button(i)}
        edges.update(instance,pressed)
    def sync_watched():
        nonlocal watch_signature
        with service.lock:
            learning=bool(service.learning and service.clock()<=service.learn_until)
            wanted={b['device'] for b in service.bindings.items.values()}
        signature=(learning,tuple(sorted(wanted)),tuple(metadata))
        if signature==watch_signature:return
        watch_signature=signature
        for instance,info in metadata.items():
            desired=(learning or info['id'] in wanted) and list(identities.values()).count(info['id'])==1
            if not desired and instance in joysticks:
                joysticks.pop(instance).quit();edges.remove(instance)
            elif desired and instance not in joysticks:
                js=pygame.joystick.Joystick(info['index']);joysticks[instance]=js
                edges.update(instance,{i for i in range(js.get_numbuttons()) if js.get_button(i)})
    try:
        for i in range(pygame.joystick.get_count()):add(i)
        while not service.stop.is_set():
            sync_watched()
            for event in pygame.event.get():
                if event.type==pygame.JOYDEVICEADDED:
                    js=pygame.joystick.Joystick(event.device_index)
                    instance=js.get_instance_id()
                    if instance not in metadata:add(event.device_index)
                    elif instance not in joysticks:js.quit()
                elif event.type==pygame.JOYDEVICEREMOVED:
                    js=joysticks.pop(event.instance_id,None)
                    identities.pop(event.instance_id,None);edges.remove(event.instance_id)
                    removed=metadata.pop(event.instance_id,None)
                    if removed:
                        for info in metadata.values():
                            if info['index']>removed['index']:info['index']-=1
                    if js:js.quit()
                    with service.lock:service.enabled=False;service.queue.clear()
                elif event.type in (pygame.JOYBUTTONDOWN,pygame.JOYBUTTONUP):
                    instance=event.instance_id
                    if instance not in joysticks:continue
                    pressed=set(edges.states.get(instance,set()))
                    if event.type==pygame.JOYBUTTONDOWN:pressed.add(event.button)
                    else:pressed.discard(event.button)
                    fresh=edges.update(instance,pressed)
                    ident=identities[instance]
                    if list(identities.values()).count(ident)>1:continue
                    for button in fresh:service.button(ident,button)
            if time.monotonic()-last_devices>1:
                devices=[]
                for instance,info in metadata.items():
                    ident=identities[instance]
                    devices.append(dict(id=ident,name=info['name'],buttons=info['buttons'],
                                        ambiguous=list(identities.values()).count(ident)>1))
                with service.lock:service.devices=devices
                last_devices=time.monotonic()
            service.stop.wait((.008 if service.enabled or service.learning else .05) if joysticks else .25)
    except Exception as exc:
        with service.lock:service.input_error='USB input stopped: '+str(exc);service.enabled=False;service.queue.clear()
    finally:pygame.joystick.quit();pygame.display.quit()
