import importlib.util
import zipfile
from pathlib import Path


def test_deployment_package_contains_no_credentials_or_runtime_data():
    path=Path(__file__).parents[1]/'examples/deploy_private_app.py'
    spec=importlib.util.spec_from_file_location('deploy_example',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    archive=module.package()
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())=={'radar_ia/__init__.py','radar_ia/hosted_api.py','radar_ia/review_api.py','radar_ia/jobs.py','radar_ia/audio.py','radar_ia/speech_markup.py','radar_ia/push.py'}
