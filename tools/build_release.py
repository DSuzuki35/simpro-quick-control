"""Build a portable Windows release; run with the project's virtualenv Python."""
import hashlib
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
NAME='SimPro Quick Control'

def finish_package(folder,destination):
    for name in ('QUICKSTART.txt','Start VR only.cmd','LICENSE'):
        shutil.copy2(ROOT/name,folder/name)
    licenses=folder/'THIRD-PARTY-LICENSES';licenses.mkdir(exist_ok=True)
    for distribution in importlib.metadata.distributions():
        for item in distribution.files or []:
            lower=str(item).lower()
            if any(word in Path(lower).name for word in ('license','copying','copyright')) and not lower.endswith(('.py','.pyc')):
                source=Path(distribution.locate_file(item))
                if source.is_file():
                    target=licenses/distribution.metadata['Name']/str(item).replace('/','_').replace('\\','_')
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for python_license in (Path(sys.base_prefix)/'LICENSE.txt',Path(sys.base_prefix)/'LICENSE'):
        if python_license.exists():shutil.copy2(python_license,licenses/'PYTHON-LICENSE.txt');break
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for file in sorted(folder.rglob('*')):
            relative=file.relative_to(folder)
            if file.is_file() and relative.parts[0]!='data':archive.write(file,Path(NAME)/relative)
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.zip.sha256').write_text(digest+'  '+destination.name+'\n','utf-8')
    print(destination)

if __name__=='__main__':
    if sys.platform!='win32':raise SystemExit('Build on Windows with Python 3.12.')
    subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name',NAME,
                    '--icon',str(ROOT/'web'/'icon.ico'),'--add-data',str(ROOT/'web')+';web','--distpath',str(ROOT/'dist'),
                    '--workpath',str(ROOT/'build'),'--specpath',str(ROOT/'build'),str(ROOT/'main.py')],cwd=ROOT,check=True)
    finish_package(ROOT/'dist'/NAME,ROOT/'dist'/'SimPro-Quick-Control-Windows-x64.zip')
