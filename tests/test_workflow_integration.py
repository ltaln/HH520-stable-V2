import json
from pathlib import Path
import subprocess
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_dispatch_schema_preserves_stable_and_adds_research():
    schema=json.loads((ROOT/'integration/chatgpt-action.openapi.json').read_text(encoding='utf-8'))
    paths=schema['paths']
    prediction=paths['/repos/ltaln/HH520-stable-V2/actions/workflows/hh520-predict.yml/dispatches']['post']
    research=paths['/repos/ltaln/HH520-stable-V2/actions/workflows/hh520-research.yml/dispatches']['post']
    assert prediction['operationId']=='startHH520Prediction'
    assert research['operationId']=='startHH520Research'
    p=paths['/repos/ltaln/HH520-stable-V2/contents/results/{request_id}.json']['get']
    assert next(x for x in p['parameters'] if x['name']=='ref')['schema']['enum']==['action-results']
    r=paths['/repos/ltaln/HH520-stable-V2/contents/{directory}/{request_id}.json']['get']
    assert next(x for x in r['parameters'] if x['name']=='ref')['schema']['enum']==['research-results']


def test_native_plugin_contract_replaces_custom_action_execution():
    instructions=(ROOT/'integration/CHATGPT_INSTRUCTIONS.md').read_text(encoding='utf-8')
    native=(ROOT/'integration/PLUGIN_NATIVE_TOOLS.md').read_text(encoding='utf-8')
    assert 'github_create_file' in instructions
    assert 'github_fetch_file' in instructions
    assert 'plugin-requests/prediction/<request_id>.json' in native
    assert 'plugin-requests/research/<request_id>.json' in native
    assert 'research-results/results/<request_id>.json' in native
    assert 'output_contract.display_rows' in native
    assert 'EXPLANATION_ONLY' in native
    assert 'connector_76869538009648d5b282a4bb21c3d157' in native
    # The plugin instructions must not route execution through legacy Actions.
    assert 'startHH520Prediction' not in instructions
    assert 'getHH520PredictionResult' not in instructions


def test_native_request_paths_are_isolated_and_exactly_once():
    bridge=(ROOT/'integration/PLUGIN_MIGRATION_BRIDGE.md').read_text(encoding='utf-8')
    assert 'research-results/results/<request_id>.json' in bridge
    assert 'github_create_file' in bridge
    assert 'github_fetch_file' in bridge
    assert '只调用一次' in (ROOT/'integration/CHATGPT_INSTRUCTIONS.md').read_text(encoding='utf-8')


def test_action_reader_forces_fresh_raw_ready_payload():
    schema=json.loads((ROOT/'integration/chatgpt-action.openapi.json').read_text(encoding='utf-8'))
    op=schema['paths']['/repos/ltaln/HH520-stable-V2/contents/results/{request_id}.json']['get']
    params={(p['in'],p['name']):p for p in op['parameters']}
    assert params[('query','ref')]['schema']['enum']==['action-results']
    assert params[('query','poll_timestamp')]['required'] is True
    assert params[('header','Accept')]['schema']['default']=='application/vnd.github.raw+json'
    description=op['description']
    assert 'status=READY' in description
    assert 'output_contract.display_rows' in description
    assert 'status=PENDING' in description
    assert 'status=FAILED' in description


def test_workflows_share_cache_lock_and_preserve_on_failure():
    for file,branch in [('hh520-predict.yml','action-results'),('hh520-research.yml','research-results')]:
        data=yaml.safe_load((ROOT/'.github/workflows'/file).read_text(encoding='utf-8'))
        assert data['jobs']['run']['concurrency']['group']=='hh520-collection-main'
        steps=data['jobs']['run']['steps']
        assert any(s.get('uses')=='actions/cache/restore@v4' for s in steps)
        save=next(s for s in steps if s.get('uses')=='actions/cache/save@v4')
        assert 'always()' in save['if']
        assert branch in steps[-1]['run']
        assert not any('clone' in s.get('run','') for s in steps)


def test_publish_to_isolated_branch_and_repeat_request(tmp_path,monkeypatch):
    def git(*args,cwd=None):
        return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
    remote=tmp_path/'remote.git'; checkout=tmp_path/'checkout'
    git('init','--bare',str(remote))
    git('clone',str(remote),str(checkout))
    git('config','user.name','Test',cwd=checkout)
    git('config','user.email','test@example.invalid',cwd=checkout)
    (checkout/'model.txt').write_text('frozen',encoding='utf-8')
    git('add','.',cwd=checkout); git('commit','-m','init',cwd=checkout)
    git('branch','-M','main',cwd=checkout); git('push','origin','main',cwd=checkout)
    from scripts.publish_action_result import publish
    monkeypatch.chdir(checkout)
    monkeypatch.setenv('GITHUB_RUN_ID','test-run')
    monkeypatch.setenv('GITHUB_SHA','original-sha')
    report=tmp_path/'result.json'; report.write_text('{"ok":true}',encoding='utf-8')
    for branch in ('action-results','research-results'):
        publish(str(report),branch,'test-request-123')
        publish(str(report),branch,'test-request-123')
        names=git('--git-dir',str(remote),'ls-tree','--name-only','-r',branch).splitlines()
        assert 'results/test-request-123.json' in names
        assert 'archive/test-request-123.json' in names
        if branch == 'research-results':
            assert 'pages/test-request-123/manifest.json' in names
    assert git('--git-dir',str(remote),'show','main:model.txt')=='frozen'
