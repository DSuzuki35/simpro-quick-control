"""Build a portable Windows release; run with the project's virtualenv Python."""
import hashlib
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import argparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import __version__
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
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'dist'/('v'+__version__));args=parser.parse_args()
    output=args.output.resolve()
    if (output/NAME/'data').exists():raise SystemExit('This output contains user data. Choose a different --output directory.')
    build=ROOT/'build';build.mkdir(exist_ok=True)
    numbers=tuple(int(n) for n in __version__.split('.'))+(0,)
    version_file=build/'version-info.txt'
    version_file.write_text("VSVersionInfo(ffi=FixedFileInfo(filevers="+repr(numbers)+",prodvers="+repr(numbers)+",mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription','SimPro Quick Control'),StringStruct('ProductName','SimPro Quick Control'),StringStruct('FileVersion','"+__version__+"'),StringStruct('ProductVersion','"+__version__+"')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])",'utf-8')
    subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name',NAME,
                    '--icon',str(ROOT/'web'/'icon.ico'),'--version-file',str(version_file),'--add-data',str(ROOT/'web')+';web','--distpath',str(output),
                    '--workpath',str(ROOT/'build'),'--specpath',str(ROOT/'build'),str(ROOT/'main.py')],cwd=ROOT,check=True)
    finish_package(output/NAME,output/'SimPro-Quick-Control-Windows-x64.zip')
