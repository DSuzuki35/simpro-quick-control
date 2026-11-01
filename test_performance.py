from service import ControlService
from test_service import Base

def test_repeated_adjustments_do_not_rewrite_unchanged_configuration(tmp_path):
    service=ControlService(Base(),tmp_path/'config.json');service.refresh();service.enable(True)
    service.adjust('total_force',1)
    saved=service.path.stat().st_mtime_ns
    for _ in range(10):service.adjust('total_force',1)
    assert service.path.stat().st_mtime_ns==saved

def test_menu_status_does_not_copy_large_snapshot(tmp_path):
    service=ControlService(Base(),tmp_path/'config.json',clock=lambda:0)
    class NoCopy:
        def __deepcopy__(self,memo):raise AssertionError('unnecessary copy')
    service.snapshot['payload']=NoCopy()
    assert service.menu_status()==(True,0)
