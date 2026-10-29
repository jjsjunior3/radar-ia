"""Pacote Lambda Linux separado da API; dependências nunca vêm da venv Windows."""
import subprocess
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULES=('audio','brief','catalog','collection','editorial','jobs','news','production','production_store','review','review_api','script','speech_markup','weekly','windows','worker')


def package_worker():
    folder=ROOT/'local-output/deploy';folder.mkdir(parents=True,exist_ok=True)
    wheels=folder/'linux-wheels';wheels.mkdir(exist_ok=True)
    requirements=ROOT/'infra/worker-requirements.txt'
    build_env=dict(os.environ,TEMP=str(folder),TMP=str(folder))
    subprocess.run([sys.executable,'-m','pip','download','--disable-pip-version-check','--only-binary=:all:',
        '--platform','manylinux2014_x86_64','--implementation','cp','--python-version','3.12',
        '--dest',str(wheels),'--find-links',str(wheels),'-r',str(requirements)],check=True,env=build_env)
    with tempfile.TemporaryDirectory(prefix='worker-build-',dir=folder) as work:
        dependencies=Path(work)/'dependencies'
        subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-compile',
            '--no-index','--find-links',str(wheels),'--only-binary=:all:','--platform','manylinux2014_x86_64',
            '--implementation','cp','--python-version','3.12','--target',str(dependencies),'-r',str(requirements)],check=True,env=build_env)
        target=folder/'worker.zip'
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(dependencies.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(dependencies).as_posix())
            archive.writestr('radar_ia/__init__.py','')
            for module in MODULES:archive.write(ROOT/f'src/radar_ia/{module}.py',f'radar_ia/{module}.py')
            archive.write(ROOT/'config/sources.json','radar_ia/config/sources.json')
    return target


if __name__=='__main__':print('Worker empacotado em:',package_worker())
