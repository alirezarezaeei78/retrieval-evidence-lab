"""Landscape adaptation of the batch workflow for an uncropped article cover."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

root=Path(__file__).resolve().parent
out=root/'experiments/2026-11-13'
r=json.loads((out/'results.json').read_text(encoding='utf-8'))
bg='#f7f5ed';ink='#173544';teal='#146d70';pale='#e3ece7'
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(12,6.75),dpi=120)
fig.patch.set_facecolor(bg);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
fig.subplots_adjust(left=0,right=1,top=1,bottom=0)
ax.text(.055,.88,'LOCAL BATCH SEARCH • WORKFLOW',color=teal,fontsize=14,fontweight='bold')
ax.text(.055,.765,'Keep failures with their evidence',color=ink,fontsize=27,fontweight='bold')
boxes=[('SOURCES',f"{r['documents']} authored docs\n{r['passages']} passages"),
       ('CORPUS-ONLY FIT','TF-IDF vocabulary\nand IDF; keyword sets'),
       ('QUERY BATCH',f"{r['query_count']} known queries\n{r['query_method_reports']} method reports"),
       ('SAVED EXPORT',f"{r['compared_accepted_passages']} accepted passages\n{r['csv_rows']} CSV rows; 6 empty")]
for i,(title,body) in enumerate(boxes):
    x=.055+i*.238
    ax.add_patch(FancyBboxPatch((x,.34),.202,.245,boxstyle='round,pad=0.01',facecolor=pale,edgecolor='none'))
    ax.text(x+.014,.54,title,fontsize=12,fontweight='bold',color=teal,va='top')
    ax.text(x+.014,.455,body,fontsize=14,color=ink,linespacing=1.65,va='top')
    if i<3:ax.annotate('',xy=(x+.229,.46),xytext=(x+.208,.46),arrowprops={'arrowstyle':'-|>','color':teal,'lw':2})
ax.text(.055,.21,'Source + fitted index/config + request hashes travel with each report.',color=ink,fontsize=17)
ax.text(.055,.13,'Known synthetic fixtures • lexical scores do not verify answers • no reranking on export',color=ink,fontsize=13)
for suffix in ['png','svg']:fig.savefig(out/('article-cover.'+suffix),facecolor=bg)
plt.close(fig)
(out/'article-cover-alt.txt').write_text('Landscape adaptation of the local batch workflow:8authored documents and24passages; corpus-only TF-IDF vocabulary/IDF and keyword token sets;22known queries give44query-method reports;79accepted passages plus no-result rows yield85CSV rows. Source, fitted-index/configuration and request hashes travel with saved JSON/CSV. Known synthetic fixtures, no reranking at export; lexical scores do not verify answers.\n',encoding='utf-8')
