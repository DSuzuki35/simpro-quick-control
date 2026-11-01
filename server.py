import hmac
import json
import secrets
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from keyboard_reader import KEY_OPTIONS

def make_server(service,web_dir,port=0):
    web_dir=Path(web_dir);token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def reply(self,status,data,content_type='application/json'):
            body=json.dumps(data).encode() if content_type=='application/json' else data
            self.send_response(status);self.send_header('Content-Type',content_type)
            if status!=200:self.close_connection=True;self.send_header('Connection','close')
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def valid_host(self):return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def do_GET(self):
            if not self.valid_host():return self.reply(403,{'error':'Invalid host'})
            path=urlsplit(self.path).path
            if path=='/api/session':return self.reply(200,{'token':token,'keyboard_keys':KEY_OPTIONS})
            if path=='/api/state':
                if not hmac.compare_digest(self.headers.get('X-Control-Token',''),token):return self.reply(403,{'error':'Open the local control page'})
                return self.reply(200,service.state())
            files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            files.update({'/vr':('vr.html','text/html; charset=utf-8'),'/vr.js':('vr.js','text/javascript; charset=utf-8'),'/vr.css':('vr.css','text/css; charset=utf-8')})
            files.update({'/icon.png':('icon.png','image/png'),'/icon.ico':('icon.ico','image/x-icon')})
            if path not in files:return self.reply(404,{'error':'Not found'})
            name,mime=files[path]
            return self.reply(200,(web_dir/name).read_bytes(),mime)
        def do_POST(self):
            origin=self.headers.get('Origin')
            allowed=(None,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
            if not self.valid_host() or origin not in allowed or not hmac.compare_digest(self.headers.get('X-Control-Token',''),token):
                return self.reply(403,{'error':'Request not allowed'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<0 or length>32768:raise ValueError('Request too large')
                data=json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(data,dict):raise ValueError('Expected an object')
                path=urlsplit(self.path).path
                if path=='/api/config':service.update_config(data)
                elif path=='/api/enable':service.enable(data['enabled'])
                elif path=='/api/learn':service.learn(data.get('action'))
                elif path=='/api/adjust':service.adjust(data['key'],data['direction'])
                elif path=='/api/show':service.activity()
                elif path=='/api/open-settings':self.server.open_settings()
                elif path=='/api/hide':self.server.hide_menu()
                elif path=='/api/quit':self.server.quit_app()
                elif path=='/api/startup':self.server.set_startup(data['enabled'])
                else:return self.reply(404,{'error':'Unknown action'})
                self.reply(200,{'ok':True})
            except (ValueError,KeyError,TypeError) as exc:self.reply(400,{'error':str(exc)})
            except Exception as exc:self.reply(503,{'error':str(exc)})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    server.open_settings=lambda:None;server.hide_menu=lambda:None;server.quit_app=lambda:None
    server.set_startup=lambda value:None
    return server
