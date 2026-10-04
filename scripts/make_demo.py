"""Build the README demo (docs/demo.gif) and, optionally, the launch video, from real output.

Every slide is an HTML page rendered by headless Chrome: the terminal slides show the output
of the commands they name, captured when this script runs them; the report slides are the
HTML report of that run; the results slide reads its figures from docs/v05-results.json. No
number is typed by hand.

  python scripts/make_demo.py                         # docs/demo.gif
  python scripts/make_demo.py --video launch.mp4      # also an MP4 (needs ffmpeg)

Needs Google Chrome (or CHROME=/path/to/chrome) and Pillow; maintainer tooling, not run in CI.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
W, H = 960, 600
LABELS = "examples/email-routing/labels.jsonl"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

STYLE = """
*{box-sizing:border-box}html,body{margin:0;width:960px;height:600px;overflow:hidden}
body{font:20px/1.45 -apple-system,"Segoe UI",Helvetica,Arial,sans-serif;color:#14213d;
background:#fff}
.wrap{padding:48px 56px;height:600px;display:flex;flex-direction:column}
.kicker{font-size:14px;letter-spacing:.14em;text-transform:uppercase;color:#0a7c86;
font-weight:700;border-bottom:3px solid #13294b;padding-bottom:10px;margin-bottom:28px}
h1{font-size:46px;line-height:1.15;color:#13294b;margin:40px 0 20px}
p.lead{font-size:23px;color:#3a4556;max-width:820px}
.term{background:#1e1e2e;color:#cdd6f4;font:17px/1.55 "SF Mono",Menlo,Consolas,monospace;
border-radius:10px;padding:26px 28px;flex:1;white-space:pre-wrap;overflow:hidden}
.term .p{color:#a6e3a1}.term .c{color:#7f849c}.term .ok{color:#a6e3a1}.term .bad{color:#f38ba8}
.cap{font-size:19px;color:#13294b;font-weight:700;margin:0 0 14px}
table{border-collapse:collapse;width:100%;font-size:21px;margin-top:6px}
th{background:#13294b;color:#fff;text-align:left;padding:10px 14px;font-size:16px}
td{border-bottom:1px solid #d9dee5;padding:12px 14px}td.r,th.r{text-align:right}
td b{color:#0a7c86;font-size:26px}
.note{font-size:14px;color:#5b6573;margin-top:16px}
.big{font:600 30px "SF Mono",Menlo,monospace;background:#f5f7fa;border:1px solid #d9dee5;
border-radius:8px;padding:18px 24px;margin:26px 0;color:#13294b}
.chips span{display:inline-block;border:2px solid #0a7c86;color:#0a7c86;border-radius:20px;
padding:6px 16px;margin:0 10px 10px 0;font-weight:700;font-size:18px}
"""


def page(body: str) -> str:
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{STYLE}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>')


def shoot(html_path: Path, png: Path, width: int = W, height: int = H, scale: float = 1) -> None:
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
                    "--virtual-time-budget=3000", f"--screenshot={png}", str(html_path)],
                   check=True, capture_output=True)


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr).strip()


def terminal(lines: list[tuple[str, str]]) -> str:
    out = []
    for kind, text in lines:
        cls = {"cmd": "p", "comment": "c", "ok": "ok", "bad": "bad"}.get(kind, "")
        prefix = "$ " if kind == "cmd" else ""
        out.append(f'<span class="{cls}">{html.escape(prefix + text)}</span>')
    return "\n".join(out)


def slides(work: Path) -> list[tuple[Path, float]]:
    ja = shutil.which("judge-audit") or "judge-audit"
    out: list[tuple[Path, float]] = []

    def add(name: str, body: str, seconds: float) -> None:
        f = work / f"{name}.html"
        f.write_text(page(body), encoding="utf-8")
        png = work / f"{name}.png"
        shoot(f, png)
        out.append((png, seconds))

    # 1 the question
    add("01-title", '<div class="kicker">judge-audit · open source</div>'
        "<h1>Can your AI judge decide alone?</h1>"
        '<p class="lead">judge-audit replays decisions your people already made and measures '
        "how much of that work an AI judge can take over, at the error you accept, with the "
        "bound attached.</p>", 3.0)

    # 2 the run, captured
    report = work / "report.html"
    cmd = [ja, "run", LABELS, "--judge", "simulated", "--target", "0.10", "--format", "html",
           "--out", str(report), "--json", str(work / "result.json"),
           "--judgments", str(work / "j.jsonl")]
    _, text = run(cmd, ROOT)
    first = text.splitlines()[0].split(" -> ", 1)[0] + " -> report.html"   # no machine path
    shown = first.split(" · ", 1)
    body = terminal([("comment", "# replay 200 labelled decisions (seeded simulator, no API key)"),
                     ("cmd", f"judge-audit run {LABELS} --judge simulated --target 0.10"),
                     ("", shown[0] + " ·"), ("ok", shown[1] if len(shown) > 1 else "")])
    add("02-run", f'<div class="cap">1 · Run the audit in shadow mode</div><div class="term">{body}</div>',
        3.5)

    # 3 + 4 the report it wrote, the answer first
    for name, scroll, caption, seconds in (
            ("03-report", "", "2 · The report opens with the answer", 4.0),
            ("04-targets", "Can I automate this?",
             "3 · Every error tolerance: share automated, threshold, out-of-sample check", 4.0)):
        copy = work / f"{name}-src.html"
        src = report.read_text(encoding="utf-8")
        if scroll:   # start the page at that section: drop everything above it
            src = src.replace("</body>", "<script>for(const h of document.querySelectorAll('h2'))"
                              f"if(h.textContent.includes({json.dumps(scroll)}))"
                              "{let n=h.previousElementSibling;while(n){const q="
                              "n.previousElementSibling;n.remove();n=q}break}</script></body>")
        copy.write_text(src, encoding="utf-8")
        raw = work / f"{name}-raw.png"
        shoot(copy, raw, width=1000, height=620)
        frame = Image.new("RGB", (W, H), "white")
        shot = Image.open(raw).convert("RGB").crop((20, 0, 1000, 560)).resize((900, 514))
        frame.paste(shot, (30, 72))
        f = work / f"{name}.html"
        f.write_text(page(f'<div class="cap">{html.escape(caption)}</div>'), encoding="utf-8")
        head = work / f"{name}-head.png"
        shoot(f, head)
        top = Image.open(head).convert("RGB").crop((0, 0, W, 72))
        frame.paste(top, (0, 0))
        png = work / f"{name}.png"
        frame.save(png)
        out.append((png, seconds))

    # 5 real data, from docs/v05-results.json
    d = json.loads((ROOT / "docs/v05-results.json").read_text(encoding="utf-8"))
    m = d["metrics"]
    rows = []
    for label, run_key in (("Jev, native probability", "jev"),
                           ("gemini-3.6-flash, verbalized", "llm-gemini-3.6-flash"),
                           ("Qwen3-8B, token log-probability", "logprob-qwen3-8b")):
        c = m[f"banking77/{run_key}"]["strict"]["certification"]["0.05"]
        p = c["pooled"]
        lo, hi = c["spread_coverage"]
        rate = f"{p['coverage'] * 100:.1f} %" if p["covered"] else "none"
        rows.append(f"<tr><td>{html.escape(label)}</td><td class='r'><b>{rate}</b></td>"
                    f"<td class='r'>{lo * 100:.1f}–{hi * 100:.1f} %</td></tr>")
    n = m["banking77/jev"]["strict"]["n"]
    add("05-real", f'<div class="cap">4 · On real data: BANKING77, {n:,} human-labelled banking '
        "queries</div><table><tr><th>Judge and confidence</th><th class='r'>Decides alone at "
        "≤ 5 % error</th><th class='r'>Range over split seeds</th></tr>" + "".join(rows)
        + "</table><p class='note'>Pre-registered v0.5 study. Public datasets, probably seen in "
        "pretraining; label noise not measured; held-out slice not run. Every caveat: "
        "docs/results/v0.5.md</p>", 5.0)

    # 6 the gate, captured
    base = str(work / "result.json")
    gate = [ja, "check", LABELS, "--judge", "simulated", "--baseline", base, "--target", "0.10"]
    rc_ok, _ = run(gate + ["--min-safe-rate", "0.10:0.60"], ROOT)
    rc_bad, msg = run(gate + ["--min-safe-rate", "0.10:0.70"], ROOT)
    last = msg.splitlines()[-1] if msg else ""
    body = terminal([("comment", "# CI gate: at least 60 % automatable at <= 10 % error"),
                     ("cmd", "judge-audit check … --min-safe-rate 0.10:0.60"),
                     ("ok", f"exit {rc_ok}"),
                     ("comment", "# raise the bar to 70 %: the build fails"),
                     ("cmd", "judge-audit check … --min-safe-rate 0.10:0.70"),
                     ("bad", last[:150]), ("bad", f"exit {rc_bad}")])
    add("06-gate", f'<div class="cap">5 · Gate every change in CI</div><div class="term">{body}</div>',
        4.0)

    # 7 how to start
    add("07-end", '<div class="kicker">judge-audit · Apache-2.0</div>'
        "<h1>Measure before you automate.</h1>"
        '<div class="big">pip install kunko-judge-audit</div>'
        '<div class="chips"><span>CLI</span><span>GitHub Action</span><span>MCP server</span>'
        "<span>Sigstore-signed releases</span></div>"
        '<p class="note" style="font-size:18px">github.com/kunko-ai-labs/judge-audit</p>', 3.5)
    return out


def write_gif(frames: list[tuple[Path, float]], dest: Path) -> None:
    images = [Image.open(p).convert("RGB").resize((W, H)) for p, _ in frames]
    pal = [im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
           for im in images]
    pal[0].save(dest, save_all=True, append_images=pal[1:], loop=0, optimize=True,
                duration=[int(s * 1000) for _, s in frames])


def write_video(frames: list[tuple[Path, float]], dest: Path, work: Path) -> None:
    listing = work / "frames.txt"
    lines = []
    for p, s in frames:
        lines += [f"file '{p}'", f"duration {s}"]
    lines.append(f"file '{frames[-1][0]}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i",
                    str(listing), "-vf", "fps=30,scale=1920:-2:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", str(dest)], check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gif", default=str(ROOT / "docs/demo.gif"))
    ap.add_argument("--video", help="also write an MP4 here (needs ffmpeg)")
    args = ap.parse_args(argv)
    if not Path(CHROME).exists():
        print(f"make_demo: Chrome not found at {CHROME}; set CHROME", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        frames = slides(Path(tmp))
        write_gif(frames, Path(args.gif))
        print(f"gif -> {args.gif}")
        if args.video:
            write_video(frames, Path(args.video), Path(tmp))
            print(f"video -> {args.video}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
