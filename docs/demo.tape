# Regenerate with: vhs docs/demo.tape   (brew install vhs)
# VHS 0.x + ffmpeg 9 fail to encode the GIF directly on macOS; frames are
# written to docs/.frames/ and assembled with:
#   ffmpeg -framerate 50 -i docs/.frames/frame-text-%05d.png \
#     -vf "fps=10,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse=dither=none" docs/demo.gif
Output docs/.frames/
Set Shell bash
Set FontSize 15
Set Width 1120
Set Height 600
Set Padding 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms

Hide
Type "source .venv/bin/activate; rm -rf /tmp/demo && mkdir /tmp/demo && cd /tmp/demo; export JA=$OLDPWD; clear"
Enter
Show

Type "# Can this AI judge decide alone? Replay decisions people already made (seeded simulator, no key)"
Enter
Type "judge-audit run $JA/examples/email-routing/labels.jsonl --judge simulated --target 0.10 | cut -c1-150"
Enter
Sleep 3s
Type "# The report opens with the answer: what share it can take, at what error, from what threshold"
Enter
Type "awk '/## Can I automate this/{f=1} f&&n++<3' audit-report.md | fold -s -w 140"
Enter
Sleep 6s
Type "clear"
Enter
Type "# CI gate: fail the build when the judge can no longer take 60 % of the work at <= 10 % error"
Enter
Type "judge-audit check $JA/examples/email-routing/labels.jsonl --judge simulated --baseline audit-result.json --target 0.10 --min-safe-rate 0.10:0.60 >/dev/null; echo exit=$?"
Enter
Sleep 3s
Type "judge-audit check $JA/examples/email-routing/labels.jsonl --judge simulated --baseline audit-result.json --target 0.10 --min-safe-rate 0.10:0.70 2>&1 | tail -1 | cut -c1-140; echo exit=$?"
Enter
Sleep 4s
Type "# Same engine in your agent: claude mcp add judge-audit -- judge-audit-mcp"
Enter
Sleep 2.5s
