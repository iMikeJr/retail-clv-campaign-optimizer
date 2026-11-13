"""Verification-only localhost access to an internal Docker network via exec/stdio.

No upstream public connections, proxy dependencies or production changes.
Run from the repository root while clv-final is on its internal network.
Stop with Ctrl-C before restoring normal Compose localhost port publishing.
"""
import base64,json,subprocess,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
UPSTREAM='''import base64,json,sys,urllib.request,urllib.error
r=json.load(sys.stdin)
request=urllib.request.Request('http://127.0.0.1:'+str(r['port'])+r['path'],data=base64.b64decode(r['body']) if r['method']=='POST' else None,headers=r['headers'],method=r['method'])
try:response=urllib.request.urlopen(request,timeout=60)
except urllib.error.HTTPError as e:response=e
with response:print(json.dumps({'status':response.status,'headers':dict(response.headers),'body':base64.b64encode(response.read()).decode()}))
'''
class Handler(BaseHTTPRequestHandler):
 def forward(self):
  port=self.server.server_port
  body=self.rfile.read(int(self.headers.get('Content-Length','0')))
  allowed={'content-type','origin','access-control-request-method','access-control-request-headers'}
  r={'port':port,'path':self.path,'method':self.command,'headers':{k:v for k,v in self.headers.items() if k.lower() in allowed},'body':base64.b64encode(body).decode()}
  service='api' if port==8000 else 'dashboard'
  p=subprocess.run(['docker','exec','-i',f'clv-final-{service}-1','python','-c',UPSTREAM],input=json.dumps(r),capture_output=True,text=True)
  if p.returncode:
   self.send_error(502,'Local verification transport unavailable');return
  response=json.loads(p.stdout);data=base64.b64decode(response['body'])
  self.send_response(response['status'])
  for k,v in response['headers'].items():
   if k.lower() not in ('content-length','connection','transfer-encoding','server','date'):self.send_header(k,v)
  self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 do_GET=forward
 do_POST=forward
 do_OPTIONS=forward
 def log_message(self,*args):pass
servers=[ThreadingHTTPServer(('127.0.0.1',port),Handler) for port in (8000,8080)]
for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
print('Local-only exec/stdio verification access ready',flush=True)
threading.Event().wait()
