"""Render README figures from the bundled computed results; no new experiment."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter

ROOT=Path(__file__).resolve().parents[2]
plt.rcParams.update({'font.family':'DejaVu Sans','svg.hashsalt':'integration-readmes-v2'})


def save(fig,kind,name):
    fig.canvas.draw()
    for text in fig.findobj(match=matplotlib.text.Text):
        if text.get_visible() and text.get_text():
            bounds=text.get_window_extent(fig.canvas.get_renderer())
            if bounds.x0 < -2 or bounds.y0 < -2 or bounds.x1 > fig.bbox.width+2 or bounds.y1 > fig.bbox.height+2:
                raise ValueError('Figure text would be clipped: '+text.get_text())
    destination=ROOT/'integrations'/kind/'assets'
    destination.mkdir(exist_ok=True)
    fig.savefig(destination/(name+'.png'),dpi=180,facecolor='white')
    fig.savefig(destination/(name+'.svg'),facecolor='white',metadata={'Date':None})
    plt.close(fig)


def results(kind):
    ppi=kind=='ppi_py'
    path=ROOT/'integrations'/kind/('example-result.json' if ppi else 'example-report.json')
    report=json.loads(path.read_text())
    fig=plt.figure(figsize=(8.6,6.3),facecolor='white')
    title=('Judge scores favor the intervention.\nHuman ratings leave its benefit unresolved.' if ppi else
           'The judge prefers the candidate.\nThe human-reference comparison is unresolved.')
    fig.text(.045,.95,title,fontsize=14.5,weight='bold',va='top',linespacing=1.35,color='#132238')
    caption=('Synthetic randomized experiment · known human effect = 0' if ppi else
             'Synthetic paired comparison · candidate − baseline')
    fig.text(.045,.79,caption,fontsize=12.5,color='#536277')
    ax=fig.add_axes([.30,.25,.65,.45])
    rows=([('Judge only','judge_only','#2563eb'),('Human ratings only','human_only','#64748b'),
           ('PPI correction','ppi','#7c3aed')] if ppi else
          [('Judge only','ai_only','#2563eb'),('Human-reference\ncorrection','corrected','#7c3aed')])
    for y,(label,key,color) in zip(reversed(range(len(rows))),rows):
        value=report[key]['estimate']
        low,high=report[key]['confidence_interval']
        if not ppi and key=='ai_only':
            ax.scatter([value],[y],s=95,color=color,zorder=3)
            text=f'{value:+.2f}'
        else:
            ax.errorbar(value,y,xerr=[[value-low],[high-value]],fmt='o',markersize=8,
                        linewidth=2.8,capsize=6,color=color,zorder=3)
            text=f'{value:+.2f}  [{low:+.2f}, {high:+.2f}]'
        ax.annotate(text,(value,y),xytext=(0,20),textcoords='offset points',
                    ha='center',color=color,fontsize=12,weight='bold')
    ax.axvline(0,color='#a8b3c1',linestyle='--',linewidth=1.3)
    ax.set_yticks(list(reversed(range(len(rows)))),[row[0] for row in rows],fontsize=12,color='#132238')
    ax.tick_params(axis='y',length=0,pad=12)
    ax.tick_params(axis='x',length=0,pad=9,labelsize=11,colors='#536277')
    ax.set_ylim(-.55,len(rows)-.35)
    ax.set_xlim((-4.5,11.5) if ppi else (-1.2,1.0))
    ax.set_xticks([-4,-2,0,2,4,6,8,10] if ppi else [-1,-.5,0,.5,1])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_: '0' if x==0 else f'{x:+g}'))
    ax.set_xlabel('Treatment effect (illustrative points)' if ppi else 'Paired difference (points)',
                  fontsize=12,color='#536277',labelpad=14)
    for spine in ax.spines.values():spine.set_visible(False)
    counts=(f"{report['labeled_units']:,} human-rated + {report['unlabeled_units']:,} independent judge-only units" if ppi else
            f"{report['pairs']['units']} prompt pairs · {report['pairs']['audited']} human-audited pairs")
    fig.text(.045,.115,counts,fontsize=12,color='#132238')
    fig.text(.045,.065,'Intervals concern each method’s own target; human-reference intervals include zero.',fontsize=10.5,color='#536277')
    fig.text(.045,.025,('PPI/human-only intervals are conservative. One synthetic draw; no coverage or cost-saving claim.' if ppi else
                        'Asymptotic interval; tiny synthetic fixture. Judge point shown without an interval.'),fontsize=10,color='#536277')
    save(fig,kind,'results')


def workflow(kind):
    ppi=kind=='ppi_py'
    fig,ax=plt.subplots(figsize=(8.6,6.2),facecolor='white')
    ax.set_axis_off()
    ax.set_xlim(0,1);ax.set_ylim(0,1)
    fig.text(.045,.96,'How the human-reference comparison works',fontsize=14.5,weight='bold',va='top',color='#132238')
    def box(x,y,w,h,title,body,color='#edf3fa'):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.012,rounding_size=.016',
                                   facecolor=color,edgecolor='#cbd5e1',linewidth=1))
        ax.text(x+w/2,y+h-.035,title,ha='center',va='top',fontsize=12,weight='bold',color='#132238')
        ax.text(x+w/2,y+.025,body,ha='center',va='bottom',fontsize=11,linespacing=1.5,color='#536277')
    if ppi:
        box(.04,.76,.92,.16,'Run the same randomized experiment in two IID samples',
            'Current notice vs new notice · one text outcome per person')
        box(.04,.48,.43,.18,'800 labeled units','Human ratings + judge scores')
        box(.53,.48,.43,.18,'4,000 unlabeled units','Judge scores · separate IDs')
        box(.04,.22,.92,.17,'Estimate each group’s human-reference mean',
            'Unlabeled prediction mean + labeled human-minus-judge residual', '#f0ebfa')
        final='Compare the group means and report an effect interval'
    else:
        box(.04,.76,.92,.16,'Run baseline and candidate on the same prompts',
            'One output per version per prompt · fixed judging rules')
        box(.04,.48,.43,.18,'Two Inspect logs','Numeric scores + matching IDs')
        box(.53,.48,.43,.18,'Human pair ratings','Both ratings for sampled pairs\nKnown inclusion probability for all')
        box(.04,.22,.92,.17,'Match, validate, and correct the paired differences',
            'Reject incomplete frames · weight sampled human-minus-judge errors', '#f0ebfa')
        final='Report the human-reference difference and its interval'
    def arrow(start,end):
        ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'->','lw':1.7,'color':'#7a899c'})
    arrow((.27,.74),(.255,.68));arrow((.73,.74),(.745,.68))
    arrow((.255,.46),(.36,.41));arrow((.745,.46),(.64,.41))
    arrow((.5,.20),(.5,.13))
    ax.text(.5,.075,final,ha='center',va='center',fontsize=12,weight='bold',color='#132238')
    fig.subplots_adjust(left=.02,right=.98,bottom=.025,top=.88)
    save(fig,kind,'workflow')


if __name__=='__main__':
    for kind in ('ppi_py','inspect_ai'):
        results(kind)
        workflow(kind)
