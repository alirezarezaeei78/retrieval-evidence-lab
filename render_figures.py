"""Static scientific figures from the recorded outputs; no decorative covers."""
import json,textwrap
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch

ROOT=Path(__file__).resolve().parent;OUT=ROOT/'experiments/2026-10-14'
INK='#142b4c';TEAL='#066f72';AMBER='#ac6a07';PALE='#e9f0f8'
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','axes.edgecolor':INK,'text.color':INK})
def finish(fig,name):
    for kind in ['png','svg']:fig.savefig(OUT/(name+'.'+kind),dpi=120,facecolor='white')
    plt.close(fig)

def workflow():
    fig,ax=plt.subplots(figsize=(10,7.5));fig.subplots_adjust(left=.03,right=.97,top=.97,bottom=.06);ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    nodes=[(.04,.67,'UTF-8 source text\nIDs + content hashes'),(.36,.67,'Paragraph passages\nExact line spans'),(.68,.67,'Document-only fit\nTF-IDF vocabulary/IDF'),(.68,.38,'Query transform\nL2 dot-product scores'),(.36,.38,'Positive score ≥ 0.15\nDeterministic top 3'),(.04,.38,'Source excerpts\nJSON + safe CSV')]
    for x,y,label in nodes:
        ax.add_patch(FancyBboxPatch((x,y),.27,.18,boxstyle='round,pad=.01',linewidth=1.5,edgecolor=TEAL,facecolor=PALE));ax.text(x+.135,y+.09,label,ha='center',va='center',fontsize=14)
    for a,b in [((.315,.76),(.35,.76)),((.635,.76),(.67,.76)),((.815,.665),(.815,.57)),((.68,.47),(.64,.47)),((.36,.47),(.315,.47))]:ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=18,lw=1.5,color=TEAL))
    ax.text(.50,.23,r'$\mathrm{idf}(t)=\ln\!\left(\frac{1+n}{1+\mathrm{df}(t)}\right)+1$',ha='center',fontsize=20)
    ax.text(.5,.135,'Schematic of the implemented lexical search; no generated answer.',ha='center',fontsize=12)
    ax.text(.5,.08,'Eight synthetic documents; 24 passages; TF-IDF uses word unigrams and L2 normalisation.',ha='center',fontsize=10)
    finish(fig,'workflow')

def outcomes(result):
    fig,ax=plt.subplots(figsize=(10,7));fig.subplots_adjust(left=.035,right=.965,top=.965,bottom=.17);ax.axis('off')
    methods=result['method_summary'];a,b=methods
    rows=[['Relevant source in top 1',f"{a['hits_at_1']} / 16",f"{b['hits_at_1']} / 16"],['Relevant source in top 3',f"{a['hits_at_3']} / 16",f"{b['hits_at_3']} / 16"],['Unsupported query accepted',f"{a['unsupported_accepted']} / 6",f"{b['unsupported_accepted']} / 6"],['Relevant query rejected',f"{a['rejected_relevant']} / 16",f"{b['rejected_relevant']} / 16"]]
    table=ax.table(cellText=rows,colLabels=['Fixture outcome','Keyword overlap','TF-IDF'],colWidths=[.53,.25,.22],cellLoc='center',loc='center',bbox=[0,.04,1,.9]);table.auto_set_font_size(False);table.set_fontsize(18)
    for (r,c),cell in table.get_celld().items():
        cell.set_edgecolor('#ccd7e4')
        if r==0:cell.set_facecolor(INK);cell.set_text_props(color='white',fontsize=16)
        elif r==3:cell.set_facecolor('#fff0d8');cell.set_text_props(color='#7c4b00')
        else:cell.set_facecolor(PALE if r%2==0 else 'white')
        if r>0 and c==0:cell.set_text_props(ha='left',fontsize=17)
    fig.text(.055,.105,'Counts from 22 authored queries on eight synthetic documents / 24 passages.',fontsize=12)
    fig.text(.055,.065,'Same corpus and queries, k=3; keyword gate >0; TF-IDF gate ≥0.15. Score scales differ.',fontsize=10)
    fig.text(.055,.025,'Fixture functionality testing; not independent validation or an enterprise accuracy estimate.',fontsize=10)
    finish(fig,'fixture-outcomes')

def failures(rows):
    cases=[r for r in rows if r['method']=='tfidf' and r['kind']=='unsupported' and r['accepted']]
    fig,ax=plt.subplots(figsize=(10,8.4));fig.subplots_adjust(left=.03,right=.97,top=.98,bottom=.07);ax.axis('off');ax.set(xlim=(0,1),ylim=(0,1))
    for i,row in enumerate(cases):
        y=.71-i*.29;p=row['results'][0]
        ax.add_patch(FancyBboxPatch((.025,y),.95,.245,boxstyle='round,pad=.01',facecolor='#fff8eb',edgecolor=AMBER,lw=1.2))
        ax.text(.045,y+.20,row['query'],fontsize=15,weight='bold')
        ax.text(.045,y+.155,f"Returned {p['passage_id']} · score {p['score']:.4f} · declared unsupported",fontsize=11,color='#7c4b00')
        snippet=p['excerpt'].splitlines()[0]
        ax.text(.045,y+.115,'\n'.join(textwrap.wrap(snippet,92)),fontsize=11,va='top')
        ax.text(.045,y+.035,'Matched terms: '+', '.join(p['matched_terms']),fontsize=10,color=TEAL)
    fig.text(.055,.03,'Executed TF-IDF examples: lexical overlap is not entailment. Inspect source limits; no answer is generated.',fontsize=10)
    finish(fig,'unsupported-matches')

if __name__=='__main__':
    result=json.loads((OUT/'results.json').read_text(encoding='utf-8'));rows=json.loads((OUT/'query-results.json').read_text(encoding='utf-8'))
    assert result['checks_passed']==40 and len(rows)==44
    workflow();outcomes(result);failures(rows)
    captions={'workflow':'Schematic of the implemented local pipeline. Document-only TF-IDF fit, source line spans, fixed positive-score gate, deterministic top-three results and structured exports. Eight synthetic documents; no generated answers.',
    'fixture-outcomes':'Measured counts on 16 relevant and six unsupported authored queries, eight synthetic documents and 24 passages. Keyword: top-one/top-three 15/16 and 15/16. TF-IDF: 15/16 and 16/16. Both accepted 3/6 unsupported queries and rejected 0/16 relevant queries. k=3; different fixed score scales/gates. Functionality fixtures, not independent validation.',
    'unsupported-matches':'Three executed unsupported TF-IDF matches. Refund after two years returned returns:L3-L4, score 0.5361, whose source limits refunds to 14 days. A legal-mandatory-authentication query returned access:L6-L7 at 0.4335 without legal evidence. An exact recovery-time guarantee query returned incident:L3-L4 at 0.2666 without a deadline. Similarity is not entailment; no answer is generated.'}
    (OUT/'figure-captions.json').write_bytes((json.dumps(captions,indent=2,ensure_ascii=False)+'\n').encode());print(json.dumps({'figures':3,'formats':['PNG','editable SVG'],'synthetic_fixture_counts':True,'video':False}))
