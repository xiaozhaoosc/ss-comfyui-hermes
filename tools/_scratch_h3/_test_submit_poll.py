import json, urllib.request, time, sys

wf = json.load(open('test_idm_vton_v3_20260814.json', encoding='utf-8'))
data = json.dumps({'prompt': wf, 'client_id': 'test_idm_v3'}).encode()
req = urllib.request.Request('http://127.0.0.1:8188/prompt', data=data, headers={'Content-Type': 'application/json'})
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    prompt_id = resp.get('prompt_id')
    print(f'Submitted: {prompt_id}')
except urllib.error.HTTPError as e:
    err = e.read().decode()
    print(f'HTTP Error {e.code}: {err[:600]}')
    sys.exit(1)

start = time.time()
for i in range(120):
    time.sleep(3)
    try:
        hist = json.loads(urllib.request.urlopen(f'http://127.0.0.1:8188/history/{prompt_id}', timeout=10).read())
        if prompt_id in hist:
            status = hist[prompt_id].get('status', {})
            if status.get('status_str') == 'error':
                msgs = status.get('messages', [])
                print(f'ERROR: {str(msgs)[:600]}')
                sys.exit(1)
            outputs = hist[prompt_id].get('outputs', {})
            if outputs:
                elapsed = time.time() - start
                print(f'SUCCESS in {elapsed:.1f}s')
                for nid, nout in outputs.items():
                    if 'images' in nout:
                        for img in nout['images']:
                            fn = img.get('filename', '?')
                            sf = img.get('subfolder', '')
                            print(f'  image: {sf}/{fn}' if sf else f'  image: {fn}')
                sys.exit(0)
        if i % 5 == 0:
            print(f'  [{i*3}s] running...')
    except Exception as e:
        print(f'  [{i*3}s] poll error: {e}')
print('TIMEOUT')
