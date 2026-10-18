from pathlib import Path
import csv,math,json
from reportlab.graphics.shapes import Drawing,Line,String,Circle,Rect,PolyLine
from reportlab.graphics import renderPDF,renderSVG
from reportlab.lib.colors import black,white,HexColor
ROOT=Path(__file__).resolve().parents[1];W=481.89
D={p.name:list(csv.DictReader(p.open(encoding='utf-8-sig'))) for p in (ROOT/'data').glob('*.csv')}
OUT=ROOT/'output/figures'
def export(d,new,old):
    OUT.mkdir(parents=True,exist_ok=True)
    renderPDF.drawToFile(d,str(OUT/(new+'.pdf')))
    (OUT/(new+'.svg')).write_text(renderSVG.drawToString(d),encoding='utf-8')
def txt(d, x, y, s, size=8, anchor='start'):
    d.add(String(x, y, str(s), fontName='Times-Roman', fontSize=size, textAnchor=anchor, fillColor=black))

def line(d, x1, y1, x2, y2, width=0.6, dash=None, color=black):
    d.add(Line(x1, y1, x2, y2, strokeWidth=width, strokeColor=color, strokeDashArray=dash))

def axes(d, x, y, w, h, maxy, ticks):
    line(d, x, y, x + w, y)
    line(d, x, y, x, y + h)
    for v in ticks:
        yy = y + h * v / maxy
        line(d, x - 3, yy, x, yy)
        txt(d, x - 6, yy - 3, str(v), 8, 'end')

def quarter_labels(d, x, y, w, qs):
    for i, q in enumerate(qs):
        txt(d, x + w * i / (len(qs) - 1), y - 13, q[:4] + '\n' if False else q[2:4] + 'Q' + q[-1], 7.5, 'middle')

def support():
    d = Drawing(W, 365)
    rr = D['Figure_1_support.csv']
    qs = sorted(set((r['quarter'] for r in rr)))
    for j, g in enumerate(['COVERAGE', 'NONCOVERAGE']):
        yy = 215 if j == 0 else 45
        x = 42
        w = 423
        h = 105
        maxy = 12 if j == 0 else 34
        txt(d, 10, yy + h + 22, 'A  Coverage environment' if j == 0 else 'B  Noncoverage environment', 10)
        axes(d, x, yy, w, h, maxy, [0, 4, 8, 12] if j == 0 else [0, 10, 20, 30, 34])
        quarter_labels(d, x, yy, w, qs)
        for k, (f, dash, mark) in enumerate([('requested_state_n', [4, 3], False), ('included_state_n', None, True), ('fully_observed_included_state_n', [1, 2], True)]):
            xy = []
            for i, q in enumerate(qs):
                r = next((r for r in rr if r['quarter'] == q and r['coverage_group'] == g))
                xx = x + i * w / 10
                v = float(r[f])
                py = yy + h * v / maxy
                xy.extend([xx, py])
                if mark:
                    d.add(Circle(xx, py, 2 if k == 1 else 1.5, strokeColor=black, fillColor=black if k == 1 else white))
            d.add(PolyLine(xy, strokeColor=black, strokeWidth=0.9, strokeDashArray=dash))
        txt(d, 10, yy - 31, 'S/M', 7.3)
        for i, q in enumerate(qs):
            r = next((r for r in rr if r['quarter'] == q and r['coverage_group'] == g))
            txt(d, x + i * w / 10, yy - 31, r['Present_with_suppression_state_n'] + '/' + r['Unknown_total_state_n'], 7.3, 'middle')
    txt(d, 42, 350, 'Jurisdictions', 8)
    for x, label, dash in [(42, 'Requested', [4, 3]), (167, 'Both channels present', None), (335, 'All returned counts numeric', [1, 2])]:
        line(d, x, 337, x + 15, 337, dash=dash)
        txt(d, x + 20, 334, label, 7.8)
    export(d, 'Figure_1', 'Figure1_Data_Reportability')

def rates(new='Figure_2', clean=False):
    d = Drawing(W, 380)
    rr = D['Figure_S3_clean_and_alternative_support.csv'] if clean else D['Table_S1_rates_all_66_scenarios.csv']
    if clean:
        rr = [r for r in rr if r['Variant_ID'] == 'F2_M10_SAME_MODEL_SUPPORT']
    qs = ['2023Q2', '2023Q3', '2023Q4', '2024Q1', '2024Q2', '2024Q3', '2024Q4', '2025Q1', '2025Q2', '2025Q3', '2025Q4']
    txt(d, 42, 365, 'Prescriptions per 100000 total Medicaid enrollees', 9)
    for x, label, dash in [(42, 'Assignment 0', [4, 3]), (175, 'Assignment 5.5', None), (320, 'Assignment 10', [1, 2])]:
        line(d, x, 351, x + 18, 351, dash=dash)
        txt(d, x + 23, 348, label, 8)
    for j, g in enumerate(['COVERAGE', 'NONCOVERAGE']):
        y = 227 if j == 0 else 65
        x = 42
        w = 423
        h = 91
        mx = 2500 if j == 0 else 60
        txt(d, 10, y + h + 12, 'A  Coverage environment' if j == 0 else 'B  Noncoverage environment', 10)
        axes(d, x, y, w, h, mx, [0, 500, 1000, 1500, 2000, 2500] if j == 0 else [0, 20, 40, 60])
        quarter_labels(d, x, y, w, qs)
        for scenario, dash in [('0.0', [4, 3]), ('5.5', None), ('10.0', [1, 2])]:
            prev = None
            for i, q in enumerate(qs):
                r = next((r for r in rr if r['coverage_group'] == g and r['quarter'] == q and (r['Suppression_Scenario'] == scenario)), None)
                if not r or not r['rate_per_100000'] or (clean and q == '2024Q1'):
                    prev = None
                    continue
                xx = x + i * w / 10
                yy = y + h * float(r['rate_per_100000']) / mx
                if prev:
                    line(d, *prev, xx, yy, 0.8, dash)
                if scenario == '5.5':
                    d.add(Circle(xx, yy, 1.7, fillColor=black, strokeColor=black))
                prev = (xx, yy)
        txt(d, 10, y - 30, 'States', 7.4)
        for i, q in enumerate(qs):
            r = next((r for r in rr if r['coverage_group'] == g and r['quarter'] == q and (r['Suppression_Scenario'] == '5.5')), None)
            s = r['included_state_n'] if r and r['rate_per_100000'] else 'NA'
            txt(d, x + i * w / 10, y - 30, s, 7.4, 'middle')
        line(d, x + 3.75 * w / 10, y, x + 3.75 * w / 10, y + h, 0.5, [2, 3], HexColor('#666666'))
    txt(d, 42, 15, 'Vertical line: March 2024 FDA event. Panel y-axis scales differ.', 8)
    export(d, new, 'FigureS2_Clean_Matched_Support' if clean else 'Figure2_Conditional_Wegovy_Rates')

def forest():
    d = Drawing(W, 390)
    rr = D['Table_2_estimates.csv']
    labels = ['Clean F0 primary', 'Historical F0', 'P1-51 domain', 'Early', 'Late', 'Earlier window', 'Later window', 'F1 state-quarter', 'F2 product-quarter', 'F3 both flexible', 'F4 linear trends']

    def panel(title, inds, y, lo, hi):
        txt(d, 8, y, title, 10)
        txt(d, 348, y, 'IRR (95% CI)', 8)
        x = 170
        w = 165
        scale = lambda v: x + (math.log(float(v)) - math.log(lo)) / (math.log(hi) - math.log(lo)) * w
        top = y - 21
        for j, i in enumerate(inds):
            r = rr[i]
            yy = top - j * 22
            txt(d, 8, yy + 2, labels[i], 8.5)
            txt(d, 8, yy - 8, f"n={r['n']}; G={r['G']}; r={r['rank']}", 7.2)
            line(d, scale(r['CI_low']), yy, scale(r['CI_high']), yy, 1)
            d.add(Circle(scale(r['IRR']), yy, 2, fillColor=black, strokeColor=black))
            txt(d, 348, yy - 2, f"{float(r['IRR']):.3f} ({float(r['CI_low']):.3f}-{float(r['CI_high']):.3f})", 7.5)
        bot = top - (len(inds) - 1) * 22 - 17
        line(d, x, bot, x + w, bot)
        vals = [0.05, 0.1, 0.5, 1, 5] if lo == 0.05 else [0.5, 1, 5, 20] if lo == 0.5 else [10, 100, 1000]
        for v in vals:
            xx = scale(v)
            line(d, xx, bot, xx, bot - 3)
            txt(d, xx, bot - 13, str(v), 7.3, 'middle')
        if lo <= 1 <= hi:
            line(d, scale(1), bot, scale(1), top + 8, 0.5, [2, 2])
    panel('A  Clean-window specifications', [0, 3, 4, 5, 6, 7, 8, 9, 10], 370, 0.05, 5)
    panel('B  Historical effective support', [1], 123, 0.5, 20)
    panel('C  Expanded requested domain', [2], 61, 10, 1000)
    export(d, 'Figure_3', 'Figure3_DDD_Domain_and_Model_Sensitivity')

def loo():
    d = Drawing(W, 390)
    rr = D['Table_S4_all_46_LOO.csv']
    txt(d, 8, 372, 'All requested jurisdictions retained; estimates are deletion diagnostics', 10)
    scale = lambda v, x: x + 62 + (math.log(v) - math.log(0.3)) / (math.log(6) - math.log(0.3)) * 120
    for j, r in enumerate(rr):
        col = j // 23
        idx = j % 23
        x = 8 + col * 240
        y = 350 - idx * 14
        state = r['Result_ID'].split('_')[-1]
        txt(d, x, y - 2, state, 8)
        if r['IRR']:
            line(d, scale(float(r['CI_low']), x), y, scale(float(r['CI_high']), x), y, 0.65)
            d.add(Circle(scale(float(r['IRR']), x), y, 1.7, fillColor=black))
            txt(d, x + 188, y - 2, f"{float(r['IRR']):.3f}", 7.5)
        else:
            txt(d, x + 44, y - 2, 'Not identifiable' if state == 'NM' else 'No effective rows', 7.5)
    for x in [8, 248]:
        line(d, scale(1, x), 34, scale(1, x), 357, 0.5, [2, 3])
        line(d, x + 62, 24, x + 182, 24)
        for v in [0.3, 1, 3, 6]:
            txt(d, scale(v, x), 10, str(v), 7.5, 'middle')
    export(d, 'Figure_S1', 'FigureS1A_All46_LOO')

def influence():
    d = Drawing(W, 350)
    rr = D['Table_S7_cluster_influence.csv']
    for j, (f, label) in enumerate([('DDD_weighted_residual_information_share', 'A  Weighted target-information share'), ('DDD_cluster_influence_variance_share', 'B  Target variance contribution share')]):
        y = 205 if j == 0 else 45
        txt(d, 10, y + 120, label, 10)
        x = 35
        w = 435
        h = 100
        axes(d, x, y, w, h, 1, [0, 0.5, 1])
        bw = w / len(rr)
        for i, r in enumerate(rr):
            v = float(r[f])
            d.add(Rect(x + i * bw + 2, y, bw - 4, max(0.01, h * v), fillColor=black, strokeColor=None))
            txt(d, x + (i + 0.5) * bw, y - 12, r['state'], 6.8, 'middle')
    export(d, 'Figure_S2', 'FigureS1B_Cluster_Influence')
def main():
    support();rates();forest();loo();influence();rates('Figure_S3',True)
if __name__=='__main__':main()
