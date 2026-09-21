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
        if branch == 'research-results':
            assert 'archive/test-request-123.json' in names
            assert 'pages/test-request-123/manifest.json' in names
    assert git('--git-dir',str(remote),'show','main:model.txt')=='frozen'
