"""Loopback-only development app for local evidence search; no remote model calls."""
from __future__ import annotations
import argparse,json,socket
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from search import ROOT,EvidenceIndex,load_documents,validate_documents,csv_report
from workbench import Workbench,batch_csv

MAX_PAYLOAD=800_000
class LocalServer(ThreadingHTTPServer):
    allow_reuse_address=False
    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass  # Do not log uploaded text or query strings.
    def reply(self,status,content,kind='application/json; charset=utf-8',filename=None):
        if not isinstance(content,bytes):content=(content if isinstance(content,str) else json.dumps(content,ensure_ascii=False)).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.end_headers();self.wfile.write(content)
    def allowed(self):
        expected=f'127.0.0.1:{self.server.server_port}'
        return self.headers.get('Host')==expected and self.headers.get('Origin',f'http://{expected}')==f'http://{expected}'
    def do_GET(self):
        if not self.allowed():self.reply(403,{'error':'Use the loopback app address.'});return
        path=urlsplit(self.path).path
        if path=='/examples':self.reply(200,{'documents':[asdict(d) for d in load_documents(ROOT/'examples/corpus')]});return
        if path=='/batch-examples':
            queries=json.loads((ROOT/'examples/queries.json').read_text(encoding='utf-8'))['evaluation']
            self.reply(200,{'queries':[{k:q[k] for k in ['id','query','relevant_sources']} for q in queries]});return
        allowed={'/':('index.html','text/html; charset=utf-8'),'/ui.js':('ui.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if path not in allowed:self.reply(404,{'error':'Page not found.'});return
        name,kind=allowed[path];self.reply(200,(ROOT/'web'/name).read_bytes(),kind)
    def do_POST(self):
        if not self.allowed():self.reply(403,{'error':'Cross-origin requests are not accepted.'});return
        if urlsplit(self.path).path not in ('/search','/export','/batch','/download'):self.reply(404,{'error':'Endpoint not found.'});return
        try:
            if urlsplit(self.path).path=='/download':
                if self.headers.get('Content-Type','').split(';')[0]!='application/x-www-form-urlencoded':raise ValueError('Download requires a local export form.')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=20_000_000:raise ValueError('Export is empty or exceeds the20MB form limit.')
                fields=parse_qs(self.rfile.read(length).decode('utf-8'),keep_blank_values=True,strict_parsing=True,max_num_fields=2)
                if set(fields)!={'format','content'} or any(len(v)!=1 for v in fields.values()):raise ValueError('Invalid export form.')
                kind=fields['format'][0]
                if kind not in ('json','csv'):raise ValueError('Choose JSON or CSV export.')
                content=fields['content'][0]
                if kind=='json':json.loads(content)
                # Echo the saved browser report as a download: no query rerun, disk writes or external transfer.
                self.reply(200,content,'application/json; charset=utf-8' if kind=='json' else 'text/csv; charset=utf-8','evidence-report.'+kind);return
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Send application/json.')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=MAX_PAYLOAD:raise ValueError('Request is empty or exceeds the 800,000-byte limit.')
            payload=json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(payload,dict):raise ValueError('Provide a JSON record.')
            documents=validate_documents(payload.get('documents'))
            if urlsplit(self.path).path=='/batch':
                report=Workbench(documents).batch(payload.get('queries'),payload.get('methods'))
                self.reply(200,{'report':report,'csv':batch_csv(report)});return
            index=EvidenceIndex(documents)
            report=index.search(payload.get('query'),payload.get('method','tfidf'))
            if urlsplit(self.path).path=='/export':self.reply(200,csv_report(report),'text/csv; charset=utf-8')
            else:self.reply(200,report)
        except (ValueError,TypeError,UnicodeError) as ex:self.reply(400,{'error':str(ex)})

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8765);args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Use a port from 1024 to 65535.')
    server=LocalServer(('127.0.0.1',args.port),Handler)
    print(f'Local-only Document Evidence Inspector: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
