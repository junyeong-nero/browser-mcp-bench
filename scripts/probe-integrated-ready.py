"""No-inference verification of MiniWoB startup and advertised UI tools."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(KITSUNE_PROJECT=str(ROOT/'artifacts/vendor/kitsune-v0.3.0'),KITSUNE_TOOL_PRESET='full',
                  PLAYWRIGHT_BROWSERS_PATH=str(ROOT/'artifacts/browsers'),PLAYWRIGHT_SKIP_BROWSER_GC='1')
from test_personal import isolated_kitsune
from kitsune_benchmark.integrated_session import BlankSession
from kitsune_benchmark.integrated_experiment import fixture_for,units,TOOLS


def probe(target,upstream,folder,fixture):
    task=fixture.begin(target);url=re.search(r'https?://\S+',task.prompt).group(0)
    origin=url.split('/miniwob/')[0]
    session=BlankSession({'target':target,'upstream':upstream,'origin':origin,
        'evidence_path':str(Path(folder)/'evidence.json'),'enabled_tools':list(TOOLS[target])})
    try:
        session.start();session.request('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'readiness-probe','version':'1'}})
        session.send({'jsonrpc':'2.0','method':'notifications/initialized'})
        messages=[];session.forward({'jsonrpc':'2.0','id':42,'method':'tools/list'},messages.append)
        names={t['name'] for t in messages[-1]['result']['tools']} & set(TOOLS[target])
        if target=='kitsune':assert names==set(TOOLS[target])
        assert session.evidence['setup_complete'] and session.evidence['initial_tabs'][0]['url']=='about:blank'
        setup_calls=session.evidence['harness_calls']
        session.tool('browser_tabs',{'action':'new','url':url})
        tabs=session.wait_inventory(lambda rows:any(t['url']==url for t in rows))
        tab=next(t for t in tabs if t['url']==url)
        session.tool('browser_tabs',{'action':'select',('index' if target=='playwright' else 'tab_id'):tab['id']})
        snapshot=session.tool('browser_snapshot',{})
        text=json.dumps(snapshot,ensure_ascii=False)
        assert 'START' in text
        return {'target':target,'ready':True,'ui_tools':len(names),'setup_calls':setup_calls,'task_page_start_visible':True}
    finally:session.close()


def main():
    results=[]
    with tempfile.TemporaryDirectory(prefix='ibr-',dir='/tmp') as folder,fixture_for(units()[0]) as fixture:
        with isolated_kitsune(folder) as upstream:results.append(probe('kitsune',upstream,folder,fixture))
    with tempfile.TemporaryDirectory(prefix='ibr-',dir='/tmp') as folder,fixture_for(units()[0]) as fixture:
        os.environ['PWTEST_SOCKETS_DIR']=folder
        upstream=['node',str(ROOT/'node_modules/@playwright/mcp/cli.js'),'--browser','firefox','--isolated','--headless','--viewport-size','1280x720']
        results.append(probe('playwright',upstream,folder,fixture))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
