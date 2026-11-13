"""Original static technical figures from the actual batch evaluation record."""
import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'experiments/2026-11-13'
R=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
BG='#f7f5ed';INK='#173544';TEAL='#146d70';PALE='#e3ece7';AMBER='#8a5316'
plt.rcParams.update({'font.family':'DejaVu Sans','text.color':INK,'svg.fonttype':'none'})


def canvas(height):
    fig,ax=plt.subplots(figsize=(10.8,height),dpi=100)
    fig.patch.set_facecolor(BG);ax.set_facecolor(BG)
    ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
    fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
    return fig,ax


def save(fig,name,alt):
    for suffix in ['png','svg']:
        fig.savefig(OUT/(name+'.'+suffix),facecolor=BG)
    (OUT/(name+'-alt.txt')).write_text(alt+'\n',encoding='utf-8')
    plt.close(fig)


def box(ax,x,y,w,h,title,body):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012',facecolor=PALE,edgecolor='none'))
    ax.text(x+.025,y+h-.035,title,fontsize=20,fontweight='bold',color=TEAL,va='top')
    ax.text(x+.025,y+h-.079,body,fontsize=17,va='top',linespacing=1.6)


fig,ax=canvas(11.2)
ax.text(.06,.95,'KEEP EVIDENCE ATTACHED',fontsize=13,color=TEAL,fontweight='bold')
ax.text(.06,.9,'One source snapshot, every query',fontsize=25,fontweight='bold')
ax.text(.06,.85,'Schematic of the tested local batch workflow',fontsize=17)
nodes=[(.63,'1  Sources and corpus-only fit','8 authored documents → 24 source passages\nTF-IDF vocabulary / IDF fit only on passages'),
       (.43,'2  Compare the same query batch','22 known queries × 2 methods → 44 reports\nOptional source labels affect diagnostics only'),
       (.23,'3  Inspect the complete report','Known / unseen terms, gate status, exact source lines\n79 accepted passages + 6 no-result entries'),
       (.03,'4  Export the saved snapshot','Source + index/config + request SHA-256\nJSON report and 85 CSV rows; no reranking')]
for y,title,body in nodes:
    box(ax,.07,y,.86,.15,title,body)
    if y>.03:ax.annotate('',xy=(.5,y-.04),xytext=(.5,y-.012),arrowprops={'arrowstyle':'-|>','color':TEAL,'lw':2.5})
save(fig,'batch-workflow','Schematic of the tested local workflow: eight authored documents become24passages. Fit TF-IDF vocabulary and IDF on passages only. Compare22known queries using keyword overlap and TF-IDF, giving44query-method reports. Optional source annotations affect diagnostics, not ranking. Preserve79accepted passages and6no-result entries. Export source, index/config and request hashes with the saved JSON and85CSV rows; no reranking at export. No generated answers or remote model calls.')

fig,ax=canvas(10.2)
ax.text(.06,.94,'MEASURED • KNOWN SYNTHETIC FIXTURES',fontsize=13,color=TEAL,fontweight='bold')
ax.text(.06,.88,'Better inspection ≠ better retrieval',fontsize=25,fontweight='bold')
ax.text(.06,.82,'Same 16 relevant + 6 unsupported questions • k = 3',fontsize=17)
ax.text(.39,.73,'Keyword',fontsize=20,fontweight='bold',ha='center')
ax.text(.76,.73,'TF-IDF',fontsize=20,fontweight='bold',ha='center')
ax.text(.39,.686,'positive overlap',fontsize=14,ha='center')
ax.text(.76,.686,'fixed gate 0.15',fontsize=14,ha='center')
kw,tf=R['summaries']
rows=[('Relevant source first',f"{kw['hits_at_1']} / {kw['relevant_queries']}",f"{tf['hits_at_1']} / {tf['relevant_queries']}"),
      ('Source Recall@3',f"{kw['macro_source_recall_at_3']:.4f}",f"{tf['macro_source_recall_at_3']:.4f}"),
      ('Unsupported accepted',f"{kw['unsupported_accepted']} / {kw['unsupported_queries']}",f"{tf['unsupported_accepted']} / {tf['unsupported_queries']}")]
for i,(label,left,right) in enumerate(rows):
    y=.59-i*.12
    ax.axhspan(y-.048,y+.046,xmin=.06,xmax=.94,color=PALE if i%2==0 else '#ffffff')
    ax.text(.08,y+.022,label,fontsize=16,fontweight='bold',va='center')
    ax.text(.39,y-.019,left,fontsize=21,ha='center',va='center',color=TEAL)
    ax.text(.76,y-.019,right,fontsize=21,ha='center',va='center',color=TEAL)
ax.text(.06,.22,'The same three unsupported questions pass both gates.',fontsize=18,fontweight='bold',color=AMBER)
ax.text(.06,.155,'New batch vs single: 0 mismatches across 44 reports.\nKnown developer-visible fixtures; not independent validation.\nScore scales / gates are not calibrated to equal acceptance.',fontsize=16,linespacing=1.7,va='top')
save(fig,'batch-outcomes','Measured comparison on the same16relevant and6unsupported authored synthetic questions, k3. Keyword positive overlap and TF-IDF fixed0.15both put the relevant source first15/16times. Macro source Recall@3 is0.9375for keyword and1.0000for TF-IDF. Both accept3/6known unsupported queries. Every relevant fixture has one annotated source. The new batch route has zero mismatches across44reports against single-query search. Known developer-visible fixtures, not independent validation; score scales and gates are not calibrated to equal acceptance.')

fig,ax=canvas(13)
ax.text(.06,.955,'MEASURED • RETAINED FAILURE CASES',fontsize=13,color=TEAL,fontweight='bold')
ax.text(.06,.91,'A matching passage may not answer',fontsize=25,fontweight='bold')
ax.text(.06,.86,'TF-IDF accepted these known unsupported questions.',fontsize=17)
for i,item in enumerate(x for x in R['unsupported_matches'] if x['method']=='tfidf'):
    y=.61-i*.245;row=item['top_result']
    ax.add_patch(FancyBboxPatch((.06,y),.88,.205,boxstyle='round,pad=0.012',facecolor=PALE,edgecolor='none'))
    ax.text(.085,y+.178,'QUERY  '+item['query'],fontsize=18,fontweight='bold',va='top',wrap=True)
    ax.text(.085,y+.12,f"{row['passage_id']}  •  score {row['score']:.4f}",fontsize=16,color=TEAL,va='top')
    excerpt=row['excerpt'].splitlines()[0]
    ax.text(.085,y+.075,textwrap.fill(excerpt,68),fontsize=17,linespacing=1.6,va='top')
ax.text(.06,.055,'Exact first source lines shown; complete passages in the report.\nAuthored synthetic policies. Scores are not answer confidence.',fontsize=15,linespacing=1.65,va='top')
save(fig,'batch-failures','Three actual accepted TF-IDF matches for known unsupported questions. Refund requests after two years matches returns:L3-L4with score0.5361, whose first line permits a refund within14days in a synthetic example. A legally mandatory authentication-factor question matches access:L6-L7at0.4335, whose first line says to use a second factor for team accounts. An exact recovery-time guarantee question matches incident:L3-L4at0.2666, whose first line asks for the service name, event time and impact in an incident report. Exact first lines shown; full passages are in the saved report. Authored synthetic policies, not legal guidance. Lexical scores are not answer confidence.')
print('Rendered three original static PNG/SVG technical figures with alt text.')
