"""Local lexical search with inspectable source spans. No generated answers."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,re
from dataclasses import dataclass,asdict
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT=Path(__file__).resolve().parent
MAX_DOCS=20;MAX_DOC_BYTES=50_000;MAX_TOTAL_BYTES=500_000;MAX_QUERY_CHARS=1000
TOKEN_PATTERN=r'(?u)\b\w\w+\b'

@dataclass(frozen=True)
class Document:
    source_id:str
    title:str
    text:str

@dataclass(frozen=True)
class Passage:
    passage_id:str
    source_id:str
    title:str
    line_start:int
    line_end:int
    excerpt:str
    document_sha256:str

def validate_documents(records):
    if not isinstance(records,list) or not 1<=len(records)<=MAX_DOCS:raise ValueError('Provide 1–20 documents.')
    docs=[];ids=set();total=0
    for r in records:
        if not isinstance(r,dict):raise ValueError('Each document must be a record.')
        source=r.get('source_id');title=r.get('title');text=r.get('text')
        if not isinstance(source,str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}',source):raise ValueError('Use a unique lowercase source ID with letters, digits, dots, dashes or underscores.')
        if source in ids:raise ValueError('Duplicate source ID: '+source)
        if not isinstance(title,str) or not title.strip() or len(title)>160:raise ValueError('Each title needs 1–160 characters.')
        if not isinstance(text,str) or not text.strip():raise ValueError('Each document needs nonempty text.')
        size=len(text.encode('utf-8'))
        if size>MAX_DOC_BYTES:raise ValueError('Each document must be at most 50,000 UTF-8 bytes.')
        total+=size
        if total>MAX_TOTAL_BYTES:raise ValueError('Total document text must be at most 500,000 UTF-8 bytes.')
        ids.add(source);docs.append(Document(source,title.strip(),text))
    return tuple(docs)

def load_documents(directory):
    directory=Path(directory)
    if not directory.is_dir() or directory.is_symlink():raise ValueError('Choose a regular document directory.')
    records=[]
    for f in sorted(directory.iterdir()):
        if f.suffix.lower() not in ('.txt','.md'):continue
        if f.is_symlink() or not f.is_file():raise ValueError('Only regular TXT/Markdown files are supported.')
        if f.stat().st_size>MAX_DOC_BYTES:raise ValueError('Document exceeds the 50,000-byte limit.')
        try:text=f.read_text(encoding='utf-8',errors='strict')
        except UnicodeError as ex:raise ValueError('Text files must use valid UTF-8.') from ex
        first=text.splitlines()[0] if text.splitlines() else ''
        title=first[2:].strip() if first.startswith('# ') else f.stem.replace('-',' ').replace('_',' ')
        records.append({'source_id':f.stem,'title':title,'text':text})
    return validate_documents(records)

def segment(docs,max_lines=8):
    if isinstance(max_lines,bool) or not isinstance(max_lines,int) or not 1<=max_lines<=50:raise ValueError('Passage line limit must be 1–50.')
    passages=[]
    for d in docs:
        lines=d.text.splitlines();digest=hashlib.sha256(d.text.encode('utf-8')).hexdigest();start=None
        for i in range(len(lines)+1):
            end=i==len(lines) or not lines[i].strip()
            if not end and start is None:start=i
            if start is not None and (end or i-start+1==max_lines):
                stop=i if end else i+1
                excerpt='\n'.join(lines[start:stop])
                passages.append(Passage(f'{d.source_id}:L{start+1}-L{stop}',d.source_id,d.title,start+1,stop,excerpt,digest));start=None
    return tuple(passages)

class EvidenceIndex:
    def __init__(self,docs):
        self.documents=tuple(docs);self.passages=segment(docs)
        if not self.passages:raise ValueError('No nonempty passages were found.')
        self.vectorizer=TfidfVectorizer(stop_words='english',strip_accents='unicode',token_pattern=TOKEN_PATTERN,ngram_range=(1,1),norm='l2',smooth_idf=True,sublinear_tf=False,dtype=np.float64)
        try:self.matrix=self.vectorizer.fit_transform([p.excerpt for p in self.passages])
        except ValueError as ex:raise ValueError('Documents contain no searchable tokens after text processing.') from ex
        self.analyzer=self.vectorizer.build_analyzer()
        self.tokens=tuple(frozenset(self.analyzer(p.excerpt)) for p in self.passages)
        self.corpus_sha256=hashlib.sha256(json.dumps([asdict(d) for d in self.documents],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def search(self,query,method='tfidf',k=3,threshold=None):
        if not isinstance(query,str) or not query.strip() or len(query)>MAX_QUERY_CHARS:raise ValueError('Enter a query with 1–1,000 characters.')
        if isinstance(k,bool) or not isinstance(k,int) or not 1<=k<=20:raise ValueError('Result count must be an integer from 1 to 20.')
        if method not in ('tfidf','keyword'):raise ValueError('Method must be tfidf or keyword.')
        threshold=0.15 if threshold is None and method=='tfidf' else 0.0 if threshold is None else threshold
        if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or not 0<=threshold<=1:raise ValueError('Threshold must be finite and between 0 and 1.')
        tokens=frozenset(self.analyzer(query))
        if method=='tfidf':scores=(self.matrix@self.vectorizer.transform([query]).T).toarray().ravel()
        else:scores=np.array([len(tokens&t)/len(tokens) if tokens else 0.0 for t in self.tokens],dtype=float)
        assert np.isfinite(scores).all()
        order=sorted(range(len(scores)),key=lambda i:(-float(scores[i]),self.passages[i].source_id,self.passages[i].line_start))
        candidates=[]
        for i in order:
            score=min(1.0,max(0.0,float(scores[i])))
            if score<=0 or score<threshold:continue
            row=asdict(self.passages[i]);row.update(score=score,matched_terms=sorted(tokens&self.tokens[i]));candidates.append(row)
            if len(candidates)==k:break
        return {'query':query,'method':method,'k':k,'threshold':float(threshold),'accepted':bool(candidates),'reason':'Lexical matches found; inspect excerpts before using them.' if candidates else 'No passage passed the lexical gate. Try specific terms or check the source documents.',
            'warning':'Lexical similarity is not proof that a passage answers the question. No answer is generated.',
            'corpus_sha256':self.corpus_sha256,'document_count':len(self.documents),'passage_count':len(self.passages),'results':candidates}

def safe_cell(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r')) else text

def csv_report(report):
    stream=io.StringIO(newline='');fields=['query','method','accepted','source_id','line_start','line_end','score','matched_terms','document_sha256','excerpt'];writer=csv.DictWriter(stream,fields,lineterminator='\n');writer.writeheader()
    rows=report['results'] or [{}]
    for row in rows:
        values={'query':report['query'],'method':report['method'],'accepted':report['accepted'],**{k:row.get(k,'') for k in fields[3:]}}
        if isinstance(values['matched_terms'],list):values['matched_terms']=' '.join(values['matched_terms'])
        writer.writerow({k:safe_cell(v) for k,v in values.items()})
    return stream.getvalue()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--documents',type=Path,default=ROOT/'examples/corpus');parser.add_argument('--query',required=True);parser.add_argument('--method',choices=['tfidf','keyword'],default='tfidf');parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=EvidenceIndex(load_documents(args.documents)).search(args.query,args.method)
    text=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.with_suffix('.json').write_text(text,encoding='utf-8');args.output.with_suffix('.csv').write_text(csv_report(report),encoding='utf-8')
    print(text,end='')
if __name__=='__main__':main()
