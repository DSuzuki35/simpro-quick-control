import copy
import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
from simpro import SimproClient,SimproError

@pytest.fixture
def rig():
    data={'servo':{'total_force':100,'mechanical_damper':8,'wheel_return_speed':43},'preset':'123','pending':None,'reads':0,'accept':True,'writes':[],'version':'V3.2.4.13771-0518ecbb'}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            method=self.path.rsplit('/',1)[-1]
            result=None
            if method=='app_get_info':result={'app_version':data['version']}
            elif method=='get_device_list': result=[{'device_uuid':'ABC','product_uuid':'00000000010B0000','product_type':'base','product_name':'Alpha EVO Ultra','param':{'filter_level':True}}]
            elif method=='device_base_get_status': result={'device_uuid':'ABC','max_torque':28,'state':2}
            elif method=='preset_get_selected_dev_config': result={'preset_uuid':data['preset'],'config':{'preset_name':'My preset'}}
            elif method=='preset_get_dev_config':
                assert body['device_uuid']=='ABC' and body['preset_uuid']==data['preset']
                data['reads']+=1
                if data['pending'] and data['reads']%2==0:
                    data['servo']=data['pending'];data['pending']=None
                result={'preset_uuid':data['preset'],'preset_name':'My preset','servos':{'1':data['servo']},'config':{'brightness':70},'light_groups':{'1':{'is_on':True,'items':[{'x':1}]}}}
            elif method=='preset_set_dev_config':
                data['writes'].append(copy.deepcopy(body))
                assert body['part_type']=='servos' and body['part_id']==1
                if data['accept']: data['pending']=body['config']
            else: raise AssertionError(method)
            encoded=json.dumps({'status':200,'result':result,'message':''}).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(encoded)));self.end_headers();self.wfile.write(encoded)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield SimproClient('http://127.0.0.1:'+str(server.server_port),confirm_timeout=.3),data
    server.shutdown();server.server_close()

def test_write_waits_for_application_and_preserves_latest_other_values(rig):
    client,data=rig
    client.snapshot()
    data['servo']['mechanical_damper']=12
    state=client.adjust('total_force',-1)
    assert state['values']['total_force']==99
    assert data['servo']['mechanical_damper']==12
    assert data['writes'][0]['config']['wheel_return_speed']==43
    assert len(data['writes'])==1

def test_acknowledgement_without_application_is_failure_and_not_retried(rig):
    client,data=rig;data['accept']=False
    with pytest.raises(SimproError): client.adjust('total_force',-1)
    assert len(data['writes'])==1

def test_preset_switch_rejects_queued_adjustment(rig):
    client,data=rig;data['preset']='456'
    with pytest.raises(SimproError): client.adjust('total_force',-1,expected_preset='123')
    assert not data['writes']

def test_unsupported_setting_cannot_send_a_write(rig):
    client,data=rig
    with pytest.raises((ValueError,SimproError)): client.adjust('firmware',1)
    assert not data['writes']

def test_reverse_survives_integer_zero_readback(rig):
    client,data=rig;data['servo']['total_force']=-1
    assert client.adjust('total_force',-1)['values']['reverse']==1
    assert data['servo']['total_force']==0
    assert client.adjust('total_force',1)['values']['reverse']==1
    assert data['servo']['total_force']==-1

def test_reverse_can_be_selected_at_zero_without_force(rig):
    client,data=rig;data['servo']['total_force']=0
    assert client.adjust('reverse',1)['values']['reverse']==1
    assert not data['writes']
    client.adjust('total_force',1)
    assert data['servo']['total_force']==-1

def test_other_versions_are_experimental_and_can_adjust(rig):
    client,data=rig;data['version']='V3.4.0.99999-future'
    state=client.adjust('total_force',-1)
    assert state['values']['total_force']==99
    assert state['compatibility']['experimental']

def test_tested_version_is_recognized(rig):
    client,data=rig
    assert not client.snapshot()['compatibility']['experimental']
