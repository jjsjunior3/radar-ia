import importlib.util
from pathlib import Path
import pytest


def module():
    path=Path(__file__).parents[1]/'examples/deploy_private_app.py'
    spec=importlib.util.spec_from_file_location('deploy_recovery',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class FakeCF:
    def __init__(self,status='ROLLBACK_COMPLETE',resource_status='DELETE_SKIPPED'):
        self.status=status;self.resource_status=resource_status;self.calls=[]
    def describe_stacks(self,**kw):return {'Stacks':[{'StackStatus':self.status,'EnableTerminationProtection':True}]}
    def list_stack_resources(self,**kw):return {'StackResourceSummaries':[{'LogicalResourceId':'ProgressTable','ResourceStatus':self.resource_status}]}
    def update_termination_protection(self,**kw):self.calls.append('disable-protection')
    def delete_stack(self,**kw):self.calls.append('delete-failed-stack')
    def get_waiter(self,name):
        self.calls.append(name)
        class Waiter:
            def wait(self,**kw): pass
        return Waiter()


def test_rollback_requires_explicit_recovery(tmp_path):
    cf=FakeCF()
    with pytest.raises(SystemExit): module().stack_exists_or_recover(cf,'test',False,tmp_path)
    assert cf.calls==[]


def test_only_failed_stack_deleted_and_inventory_saved(tmp_path):
    cf=FakeCF()
    assert module().stack_exists_or_recover(cf,'test',True,tmp_path) is False
    assert cf.calls==['disable-protection','delete-failed-stack','stack_delete_complete']
    assert (tmp_path/'failed-stack-inventory.json').exists()


def test_healthy_stack_is_never_deleted(tmp_path):
    cf=FakeCF(status='CREATE_COMPLETE')
    assert module().stack_exists_or_recover(cf,'test',True,tmp_path) is True
    assert cf.calls==[]


def test_unexpected_live_resource_blocks_recovery(tmp_path):
    cf=FakeCF(resource_status='CREATE_COMPLETE')
    with pytest.raises(SystemExit): module().stack_exists_or_recover(cf,'test',True,tmp_path)
    assert cf.calls==[]


def test_no_lambda_reserved_capacity_in_portable_template():
    import json
    t=json.loads((Path(__file__).parents[1]/'infra/private-app.json').read_text())
    assert 'ReservedConcurrentExecutions' not in t['Resources']['ApiFunction']['Properties']
