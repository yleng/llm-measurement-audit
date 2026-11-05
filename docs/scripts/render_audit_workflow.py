"""Show how the bundled synthetic audit changes each randomized-group mean."""
from pathlib import Path
import csv
import json
import math
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.text import Text

ROOT=Path(__file__).resolve().parents[2]
BLUE='#245caa'; GREEN='#137768'; PURPLE='#7047a3'; INK='#172b42'; MUTED='#52657a'
plt.rcParams.update({'font.family':'DejaVu Sans','svg.hashsalt':'llmaudit-workflow-v4'})


def render():
    with (ROOT/'examples/experiment.csv').open() as handle:
        rows=list(csv.DictReader(handle))
    report=json.loads((ROOT/'examples/experiment-report.json').read_text())
    groups=[]
    for arm in ('0','1'):
        group=[r for r in rows if r['arm']==arm]
        audited=[r for r in group if r['audited']=='1']
        mean=statistics.mean(float(r['ai_score']) for r in group)
        adjustment=math.fsum((float(r['human_label'])-float(r['ai_score']))/
                            float(r['audit_probability']) for r in audited)/len(group)
        groups.append(dict(mean=mean,adjustment=adjustment,corrected=mean+adjustment,
                           units=len(group),audited=len(audited)))
    assert math.isclose(groups[1]['corrected']-groups[0]['corrected'],report['corrected']['estimate'],abs_tol=1e-12)
    fig,ax=plt.subplots(figsize=(9.5,7.4),facecolor='white')
    ax.set_position([0,0,1,1]);ax.set_xlim(0,100);ax.set_ylim(0,100);ax.set_axis_off()
    def text(x,y,value,size=13,color=INK,weight='normal',ha='left'):
        ax.text(x,y,value,fontsize=size,color=color,weight=weight,ha=ha,va='center',linespacing=1.4)
    def box(x,y,w,h,fill,edge):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0,rounding_size=1.3',
                                  facecolor=fill,edgecolor=edge,linewidth=1.1))
    text(5,96,'Did the new notice improve comprehension?',14.5,weight='bold')
    text(5,91,'Synthetic randomized experiment · all values computed from the bundled example',11.5,MUTED)
    text(26,84,'CURRENT NOTICE',13,weight='bold',ha='center')
    text(74,84,'NEW NOTICE',13,weight='bold',ha='center')

    text(5,78,'1  LLM scores every answer',13,BLUE,'bold')
    text(95,78,f"Judge-only gain: {report['ai_only']['estimate']:+.2f}",12,BLUE,'bold',ha='right')
    for x,group in zip((5,53),groups):
        box(x,65,42,10,'#f1f6fc','#cbdbee')
        text(x+21,71,f"{group['mean']:.1f} points",14.5,BLUE,'bold',ha='center')
        text(x+21,67,f"{group['units']:,} scored answers",11,MUTED,ha='center')

    text(5,60,'2  Humans review a random sample',13,GREEN,'bold')
    text(95,60,f"{sum(g['audited'] for g in groups)} rated answers",12,GREEN,ha='right')
    for x,group in zip((5,53),groups):
        box(x,44,42,13,'#edf7f3','#c5dfd6')
        text(x+21,54,'Audit correction to the group mean',11.5,GREEN,ha='center')
        text(x+21,49.5,f"{group['adjustment']:+.1f} points",14.5,GREEN,'bold',ha='center')
        text(x+21,46,f"From {group['audited']} sampled human ratings",11.5,MUTED,ha='center')
    text(50,40.5,'Use human-minus-judge errors, weighted by 1 / sampling probability.',11,MUTED,ha='center')

    text(5,35,'3  Add each audit correction to its LLM group mean',13,PURPLE,'bold')
    for x,group in zip((5,53),groups):
        box(x,23,42,9,'#f5f1fb','#d8cbe8')
        text(x+21,27.5,f"{group['mean']:.1f} {group['adjustment']:+.1f} = {group['corrected']:.1f}",14.5,PURPLE,'bold',ha='center')
    for start,end in [((26,22),(38,19)),((74,22),(62,19))]:
        ax.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=14,color=PURPLE,lw=1.7))
    box(5,4,90,14,'#f5f1fb','#d8cbe8')
    text(50,15,'4  Compare the corrected means: new − current',12,PURPLE,'bold',ha='center')
    text(50,11,f"Human-reference effect: {report['corrected']['estimate']:+.2f} points",14.5,INK,'bold',ha='center')
    low,high=report['corrected']['confidence_interval']
    text(50,6.8,f'95% interval: {low:+.2f} to {high:+.2f}  →  improvement remains unresolved',12,INK,ha='center')
    text(50,1.8,'Synthetic example · rounded group means · no coverage or cost-saving claim.',11,MUTED,ha='center')
    fig.canvas.draw()
    for item in fig.findobj(match=Text):
        if item.get_visible() and item.get_text():
            bounds=item.get_window_extent(fig.canvas.get_renderer())
            assert bounds.x0>=-1 and bounds.y0>=-1 and bounds.x1<=fig.bbox.width+1 and bounds.y1<=fig.bbox.height+1,item.get_text()
    destination=ROOT/'docs/assets/audit-workflow'
    fig.savefig(destination.with_suffix('.png'),dpi=180,facecolor='white')
    fig.savefig(destination.with_suffix('.svg'),facecolor='white',metadata={'Date':None})
    plt.close(fig)


if __name__=='__main__':
    render()
