"""Rebuild documentation images and report snapshots from the synthetic example.

Requires matplotlib for documentation rendering only. Package runtime stays stdlib-only.
"""
from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter

from llmaudit.cli import main


def render():
    with tempfile.TemporaryDirectory(prefix='llmaudit-readme-') as temporary:
        prefix = Path(temporary) / 'paired-report'
        status = main(['--data', str(ROOT / 'examples/paired.csv'),
                       '--design', str(ROOT / 'examples/paired_design.json'),
                       '--output', str(prefix)])
        if status:
            raise RuntimeError('synthetic example failed; preview was not rebuilt')
        report = json.loads(prefix.with_suffix('.json').read_text())
        for suffix in ('.json', '.md'):
            (ROOT / 'examples' / ('paired-report' + suffix)).write_bytes(prefix.with_suffix(suffix).read_bytes())

    ai = report['ai_only']['estimate']
    corrected = report['corrected']['estimate']
    low, high = report['corrected']['confidence_interval']
    confidence = 100 * (1-report['corrected']['alpha'])
    pairs = report['pairs']
    unresolved = low <= 0 <= high
    readout = ('The human-reference interval crosses zero.' if unresolved else
               'The human-reference interval excludes zero.')

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.hashsalt': 'llmaudit-readme-v1'})
    fig = plt.figure(figsize=(9, 5.4), facecolor='#f8fafc')
    fig.text(.07, .93, 'Compare two checkpoints', fontsize=12.5, weight='bold', color='#0f172a')
    fig.text(.07, .878, 'Candidate − baseline · synthetic example', fontsize=12.5, color='#475569')

    for left, label, value, color in [
        (.07, 'LLM judge', ai, '#2563eb'),
        (.52, 'Human reference', corrected, '#7c3aed'),
    ]:
        card = FancyBboxPatch((left, .66), .41, .165, transform=fig.transFigure,
                              boxstyle='round,pad=0.012,rounding_size=0.018',
                              facecolor='white', edgecolor='#e2e8f0', linewidth=1)
        fig.add_artist(card)
        fig.text(left+.025, .775, label, fontsize=12.5, color='#475569')
        fig.text(left+.025, .694, f'{value:+.2f}', fontsize=12.5, weight='bold', color=color)
        fig.text(left+.245, .704, 'points', fontsize=12, color='#64748b')

    ax = fig.add_axes([.285, .34, .62, .255], facecolor='#f8fafc')
    ax.axvline(0, color='#94a3b8', linestyle=(0, (4, 4)), linewidth=1.4, zorder=0)
    ax.scatter([ai], [1], s=115, color='#2563eb', zorder=3)
    ax.errorbar(corrected, 0, xerr=[[corrected-low], [high-corrected]], fmt='o',
                color='#7c3aed', markersize=9, linewidth=3, capsize=7, zorder=3)
    ax.set_yticks([1, 0], ['Judge only', 'Human audited'], fontsize=12, color='#334155')
    ax.tick_params(axis='y', length=0, pad=15)
    ax.tick_params(axis='x', labelsize=12, colors='#64748b', length=0, pad=8)
    ax.set_xlim(min(low, 0)-.18, max(ai, high, 0)+.18)
    ax.set_xticks([-1, -.5, 0, .5])
    ax.set_ylim(-.6, 1.6)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: '0' if abs(value)<1e-10 else f'{value:+.1f}'))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel('Score difference (points)', fontsize=12.5, color='#64748b', labelpad=11)

    fig.text(.07, .19, f'{confidence:g}% human-reference interval:  {low:+.2f} to {high:+.2f}',
             fontsize=12.5, weight='bold', color='#334155')
    fig.text(.07, .132, readout, fontsize=12.5, color='#475569')
    fig.text(.07, .064, f"{pairs['units']} prompt pairs · {pairs['audited']} audited pairs · asymptotic interval",
             fontsize=11.5, color='#64748b')
    fig.text(.07, .025, 'Visual summary of the bundled synthetic report; not empirical evidence.',
             fontsize=10.5, color='#64748b')
    assets = ROOT / 'docs/assets'
    assets.mkdir(parents=True, exist_ok=True)
    fig.savefig(assets / 'paired-example.png', dpi=180, facecolor=fig.get_facecolor())
    fig.savefig(assets / 'paired-example.svg', facecolor=fig.get_facecolor(), metadata={'Date': None})
    plt.close(fig)


if __name__ == '__main__':
    render()
