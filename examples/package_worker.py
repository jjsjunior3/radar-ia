"""Pacote Lambda Linux separado da API; dependências nunca vêm da venv Windows."""
import subprocess
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULES=('audio','brief','catalog','collection','editorial','jobs','news','production','production_store','review','review_api','script','speech_markup','weekly','windows','worker','push','notifications')


def package_runtime(name='worker',requirements_file='worker-requirements.txt',extra_modules=()):
    folder=ROOT/'local-output/deploy';folder.mkdir(parents=True,exist_ok=True)
    wheels=folder/'linux-wheels';wheels.mkdir(exist_ok=True)
    requirements=ROOT/'infra'/requirements_file
    build_temp=Path(os.getenv('RADAR_BUILD_TEMP',str(folder)));build_temp.mkdir(parents=True,exist_ok=True)
    build_env=dict(os.environ,TEMP=str(build_temp),TMP=str(build_temp))
    if name=='worker':
        subprocess.run([sys.executable,'-m','pip','wheel','--disable-pip-version-check','--quiet','--no-deps','--wheel-dir',str(wheels),'http-ece==1.2.1'],check=True,env=build_env)
    subprocess.run([sys.executable,'-m','pip','download','--disable-pip-version-check','--quiet','--only-binary=:all:',
        '--platform','manylinux2014_x86_64','--implementation','cp','--python-version','3.12',
        '--dest',str(wheels),'--find-links',str(wheels),'-r',str(requirements)],check=True,env=build_env)
    with tempfile.TemporaryDirectory(prefix='worker-build-',dir=folder,ignore_cleanup_errors=True) as work:
        dependencies=Path(work)/'dependencies'
        subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--quiet','--no-compile',
            '--no-index','--find-links',str(wheels),'--only-binary=:all:','--platform','manylinux2014_x86_64',
            '--implementation','cp','--python-version','3.12','--target',str(dependencies),'-r',str(requirements)],check=True,env=build_env)
        target=folder/(name+'.zip')
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(dependencies.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(dependencies).as_posix())
            archive.writestr('radar_ia/__init__.py','')
            for module in MODULES+tuple(extra_modules):archive.write(ROOT/f'src/radar_ia/{module}.py',f'radar_ia/{module}.py')
            archive.write(ROOT/'config/sources.json','radar_ia/config/sources.json')
    return target


def package_worker():return package_runtime()

def package_editorial():return package_runtime('editorial','editorial-requirements.txt',('scheduled_editorial',))

if __name__=='__main__':print('Worker empacotado em:',package_worker())
