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

Type "# Audit a judge in shadow mode: it decides, humans already decided, we compare"
Enter
Type "judge-audit run $JA/examples/email-routing/labels.jsonl --judge simulated"
Enter
Sleep 2.5s
Type "# The three questions a buyer asks, answered from the evidence"
Enter
Type "sed -n '3,12p' audit-report.md"
Enter
Sleep 4s
Type "clear"
Enter
Type "# Same audit, real vendor: Jev's routing run (raw checkpoint committed in the repo)"
Enter
Type "sed -n '5,16p' $JA/docs/audit-jev-router.md"
Enter
Sleep 6s
Type "# CI gate: fail the build when the judge gets less honest than the baseline"
Enter
Type "judge-audit check $JA/examples/email-routing/labels.jsonl --judge simulated --baseline audit-result.json; echo exit=$?"
Enter
Sleep 3s
