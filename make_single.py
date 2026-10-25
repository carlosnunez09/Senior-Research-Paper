import csv, os, re
b = chr(92)
os.chdir(r"C:\Users\Carlo\OneDrive\Desktop\Senior-Research-2026-GoDot-master\paper")
s = open('main.tex', encoding='utf-8').read()
files = sorted(set(re.findall(r'data/([A-Za-z0-9_]+\.csv)', s)))


def compact(path):
    rows = list(csv.reader(open('data/' + path)))
    header = rows[0]
    keep = [i for i, h in enumerate(header)
            if h not in ('n_runs', 'pass_runs', 'phase', 'clients')]
    out = [','.join(header[i] for i in keep)]
    for r in rows[1:]:
        vals = []
        for i in keep:
            v = r[i]
            try:
                v = f'{float(v):.4g}' if abs(float(v)) < 1e4 else f'{float(v):.0f}'
            except ValueError:
                pass
            vals.append(v)
        out.append(','.join(vals))
    return '\n'.join(out)


blocks = []
for f in files:
    name = 'ns_' + f
    blocks.append(f"{b}begin{{filecontents*}}[overwrite]{{{name}}}\n{compact(f)}\n{b}end{{filecontents*}}\n")
    s = s.replace('data/' + f, name)

head = ("% ============================================================================\n"
        "% NodeStrike paper: ONE self-contained file.\n"
        "% All plot data is embedded below (filecontents) and is written to ns_*.csv\n"
        "% next to this file when you compile. Compile with:  pdflatex <this file> (twice)\n"
        "% Needs: pgfplots (with groupplots, fillbetween). No other files required.\n"
        "% ============================================================================\n\n")
open('NodeStrike_paper_single.tex', 'w', encoding='utf-8').write(head + '\n'.join(blocks) + '\n' + s)
print(len(files), 'data files embedded')
