import argparse
import logging
import sys
import threading
from pathlib import Path
from simpro import SimproClient
from service import ControlService
from server import make_server
from input_reader import run_inputs
from keyboard_reader import run_keyboard
from version import __version__

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--headless',action='store_true');parser.add_argument('--port',type=int,default=18761)
    parser.add_argument('--version',action='version',version=__version__)
    parser.add_argument('--data-dir');parser.add_argument('--startup',action='store_true');args=parser.parse_args()
    root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
    resources=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    data=Path(args.data_dir) if args.data_dir else root/'data';data.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=data/'controller.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    service=ControlService(SimproClient(),data/'config.json')
    from startup import enabled as startup_enabled,set_enabled as set_startup
    service.startup_enabled=startup_enabled()
    if args.startup:service.visibility.last_activity-=601;service.quiet_startup=True
    try:server=make_server(service,resources/'web',args.port)
    except OSError:
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{args.port}/');return
    url=f'http://127.0.0.1:{server.server_port}/'
    server.quit_app=lambda:service.stop.set()
    def configure_startup(value):
        set_startup(value);service.startup_enabled=startup_enabled()
    server.set_startup=configure_startup
    (data/'local-url.txt').write_text(url,'utf-8')
    for target in (service.run,lambda:run_inputs(service),lambda:run_keyboard(service),server.serve_forever):threading.Thread(target=target,daemon=True).start()
    try:
        if args.headless:
            print(url,flush=True)
            service.stop.wait()
        else:
            from desktop import run_desktop
            run_desktop(service,server,url,data)
    except Exception:
        logging.exception('Startup failed')
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'Could not open Wheelbase Control. See data/controller.log in the app folder.','Wheelbase Control',0x10)
    finally:service.stop.set();server.shutdown();server.server_close()

if __name__=='__main__':main()
