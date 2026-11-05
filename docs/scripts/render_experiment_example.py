"""Generate a synthetic randomized example, CLI report, and article figures.

No model calls or participant data. Matplotlib is a documentation dependency only.
Seeds are fixed in advance; this is one illustrative draw, not a coverage study.
"""
from pathlib import Path
import csv
import json
import math
import random
import statistics
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from llmaudit.cli import main

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def contrast(groups):
    estimate = statistics.mean(groups[1]) - statistics.mean(groups[0])
    se = math.sqrt(sum(statistics.variance(g) / len(g) for g in groups))
    z = statistics.NormalDist().inv_cdf(.975)
    return dict(estimate=estimate, standard_error=se,
                confidence_interval=[estimate-z*se, estimate+z*se])


def render():
    assignment, outcome, noise, audit = [random.Random(s) for s in (401, 402, 403, 404)]
    rows, humans, sampled = [], [[], []], [[], []]
    for i in range(2000):
        arm = int(assignment.random() < .5)
        human = 50 + outcome.gauss(0, 10)  # H(0)=H(1): zero individual causal effect.
        score = human + 8*arm + noise.gauss(0, 3)
        selected = int(audit.random() < .2)
        humans[arm].append(human)
        if selected:
            sampled[arm].append(human)
        rows.append(dict(record_id=f'sim-{i:04d}', arm=arm,
                         ai_score=repr(score), audited=selected,
                         human_label=repr(human) if selected else '', audit_probability=.2))
    examples = ROOT / 'examples'
    with (examples / 'experiment.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    config = json.loads((examples / 'design.json').read_text())
    config.update(score_protocol='synthetic-experiment-v1',
                  human_reference='Synthetic comprehension points; fabricated labels and scores',
                  outcome_units='illustrative points', fold_seed='fixed-before-labels')
    (examples / 'experiment_design.json').write_text(json.dumps(config, indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='llmaudit-experiment-') as temporary:
        prefix = Path(temporary) / 'experiment-report'
        if main(['--data', str(examples / 'experiment.csv'), '--design',
                 str(examples / 'experiment_design.json'), '--output', str(prefix)]):
            raise RuntimeError('CLI failed')
        report = json.loads(prefix.with_suffix('.json').read_text())
        for suffix in ('.json', '.md'):
            (examples / ('experiment-report'+suffix)).write_bytes(prefix.with_suffix(suffix).read_bytes())
    summary = dict(synthetic=True, units=2000, audit_probability=.2,
                   audited=sum(r['audited'] for r in rows),
                   seeds=dict(assignment=401, outcome=402, noise=403, audit=404),
                   population_effect=0, injected_arm_score_bonus=8,
                   human_noise_sd=10, judge_noise_sd=3,
                   full_frame_human_difference=contrast(humans)['estimate'],
                   human_only=contrast(sampled), ai_only=report['ai_only'],
                   corrected=report['corrected'])
    (examples / 'experiment-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    plt.rcParams.update({'font.family':'DejaVu Sans', 'svg.hashsalt':'llmaudit-experiment-v1',
                         'font.size':12, 'axes.spines.top':False, 'axes.spines.right':False})
    assets = ROOT / 'docs/assets'
    fig, ax = plt.subplots(figsize=(8.5, 4.9), facecolor='white')
    colors = ['#2563eb', '#64748b', '#7c3aed']
    for y, key, color in zip([2, 1, 0], ['ai_only','human_only','corrected'], colors):
        result = summary[key]
        value = result['estimate']
        low, high = result['confidence_interval']
        ax.errorbar(value, y, xerr=[[value-low],[high-value]], fmt='o',
                    color=color, markersize=9, capsize=6, linewidth=2.5)
        ax.annotate(f'{value:+.2f}  [{low:+.2f}, {high:+.2f}]', (value, y),
                    xytext=(0, 16), textcoords='offset points', ha='center', fontsize=12, color=color)
    ax.axvline(0, color='#94a3b8', linestyle='--', linewidth=1.2)
    ax.set_yticks([2,1,0], ['Judge only\nAll 2,000 scores',
                          f'Human only\n{summary["audited"]} sampled ratings',
                          'Human-reference correction\nScores + sampled ratings'])
    ax.set_ylim(-.65,2.7)
    ax.set_xlim(-5,11)
    ax.set_xlabel('New notice − current notice (illustrative points)')
    ax.spines['left'].set_visible(False)
    ax.tick_params(axis='y', length=0, pad=12)
    fig.suptitle('Random assignment does not remove scoring error',
                 fontsize=14, weight='bold', x=.035, ha='left', y=.97)
    fig.text(.035,.88, 'Synthetic example · zero human-reference effect by construction', color='#475569')
    fig.text(.035,.055, 'Bars: asymptotic 95% intervals for each estimator’s own target.', fontsize=10, color='#475569')
    fig.text(.035,.015, 'One simulated draw; no real people or LLM calls. Not a coverage or cost-saving study.', fontsize=10, color='#475569')
    fig.subplots_adjust(left=.32,right=.97,bottom=.22,top=.80)
    save(fig, assets / 'experiment-results')

    fig, ax = plt.subplots(figsize=(8.5,4.6), facecolor='white')
    ax.set_axis_off()
    boxes = [(.03,.61,.39,.23,'Randomly assign participants', 'Current notice or new notice\nCollect one text answer per person'),
             (.57,.61,.39,.23,'Score every answer', 'Use the same frozen LLM judge\nAn arm-specific error can remain'),
             (.03,.19,.39,.24,'Randomly audit answers', 'Freeze the human rubric\nHere: independent 20% inclusion'),
             (.57,.19,.39,.24,'Estimate the reference effect', 'Correct scores with sampled errors\nReport the difference + interval')]
    from matplotlib.patches import FancyBboxPatch
    for x,y,w,h,title,body in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.012',
                                   facecolor='#f1f5f9',edgecolor='#cbd5e1',transform=ax.transAxes))
        ax.text(x+.02,y+h-.03,title,transform=ax.transAxes,fontsize=11.5,weight='bold',va='top')
        ax.text(x+.02,y+h-.115,body,transform=ax.transAxes,fontsize=10.5,va='top',linespacing=1.6)
    for start,end in [((.44,.73),(.55,.73)),((.225,.59),(.225,.45)),
                      ((.44,.31),(.55,.31)),((.765,.59),(.765,.45))]:
        ax.annotate('',xy=end,xytext=start,xycoords='axes fraction',
                    arrowprops=dict(arrowstyle='->',color='#64748b',lw=1.7))
    fig.suptitle('Two randomizations, two different jobs',fontsize=14,weight='bold',x=.05,ha='left')
    fig.text(.05,.045,'Treatment assignment enables the causal comparison; audit sampling anchors its measurement.',fontsize=11,color='#475569')
    fig.subplots_adjust(left=.02,right=.98,bottom=.10,top=.89)
    save(fig, assets / 'experiment-workflow')
    print(json.dumps(summary, indent=2))


def save(fig, path):
    fig.savefig(path.with_suffix('.png'), dpi=180, facecolor='white')
    fig.savefig(path.with_suffix('.svg'), metadata={'Date':None}, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    render()
