# -*- coding: utf-8 -*-
import json, time, urllib.request, websocket, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
tg=json.loads(op.open('http://127.0.0.1:9222/json', timeout=5).read().decode())
cand=[t for t in tg if t.get('type')=='page' and 'flow.google.com/project' in t.get('url','')]
for t in cand: print('CAND', t['url'], '|', t.get('title'))
t=cand[0]
ws=websocket.create_connection(t['webSocketDebuggerUrl'], timeout=15, suppress_origin=True)
rid=0
def send(m,p=None):
    global rid
    rid+=1
    ws.send(json.dumps({'id':rid,'method':m,'params':p or {}}))
    t0=time.time()
    while True:
        d=json.loads(ws.recv())
        if d.get('id')==rid:
            return d, time.time()-t0
        if time.time()-t0>20: return None, time.time()-t0
print('EVAL', send('Runtime.evaluate', {'expression':'document.title','returnByValue':True}))
print('EVAL2', send('Runtime.evaluate', {'expression':"(()=>{const b=document.querySelector(\"button[aria-label='Settings trigger']\");if(!b)return null;const r=b.getBoundingClientRect();return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vw:innerWidth,vh:innerHeight};})()",'returnByValue':True}))
print('MOUSE', send('Input.dispatchMouseEvent', {'type':'mouseMoved','x':100,'y':100}))
print('SCREEN', send('Runtime.evaluate', {'expression':'JSON.stringify({w:innerWidth,h:innerHeight,vis:document.visibilityState})','returnByValue':True}))
