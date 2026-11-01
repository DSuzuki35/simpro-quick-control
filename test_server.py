import json
import threading
import urllib.request
import urllib.error
import pytest
from http.client import HTTPConnection
from server import make_server
from service import ControlService
from test_service import Base

def test_http_rejects_cross_origin_and_missing_token(tmp_path):
    (tmp_path/'index.html').write_text('<html>test</html>')
    svc=ControlService(Base(),tmp_path/'config.json');svc.refresh()
    http=make_server(svc,tmp_path);threading.Thread(target=http.serve_forever,daemon=True).start()
    url='http://127.0.0.1:'+str(http.server_port)
    try:
        token=json.load(urllib.request.urlopen(url+'/api/session'))['token']
        def post(headers):
            return urllib.request.urlopen(urllib.request.Request(url+'/api/enable',data=b'{"enabled":true}',headers={'Content-Type':'application/json',**headers}))
        with pytest.raises(urllib.error.HTTPError) as e:post({})
        assert e.value.code==403
        with pytest.raises(urllib.error.HTTPError) as e:post({'X-Control-Token':token,'Origin':'https://example.org'})
        assert e.value.code==403
        assert not svc.state()['enabled']
        with post({'X-Control-Token':token,'Origin':url}) as response:assert response.status==200
        assert svc.state()['enabled']
        with pytest.raises(urllib.error.HTTPError):urllib.request.urlopen(url+'/../config.json')
    finally:http.shutdown();http.server_close()

def test_browser_polling_reuses_its_http_connection(tmp_path):
    svc=ControlService(Base(),tmp_path/'config.json');svc.refresh()
    http=make_server(svc,tmp_path);threading.Thread(target=http.serve_forever,daemon=True).start()
    connection=HTTPConnection('127.0.0.1',http.server_port)
    try:
        connection.request('GET','/api/session');response=connection.getresponse();token=json.loads(response.read())['token']
        original_socket=connection.sock;assert original_socket is not None
        connection.request('GET','/api/state',headers={'X-Control-Token':token})
        response=connection.getresponse();assert json.loads(response.read())['connected']
        assert connection.sock is original_socket
    finally:connection.close();http.shutdown();http.server_close()
