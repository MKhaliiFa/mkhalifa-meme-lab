#!/usr/bin/env bash
# Every 5 minutes (timer mkhalifa-meme-update): a new commit on GitHub main -> tests -> restart.
# A failing commit is not installed (the running version stays). Public repo: no key needed.
set -uo pipefail
D=/opt/mkhalifa-meme-lab
OUT=/opt/mkhalifa/data/meme          # the live bot reads this folder (its data disk); root copies into it
mkdir -p "$OUT"
# 1) hand the summary and a status note to the bot's daily report / dashboard (root: the lab user cannot
#    enter /opt/mkhalifa, which holds the bot's secrets)
[ -f "$D/data/summary.json" ] && cp -f "$D/data/summary.json" "$OUT/summary.json.tmp" && mv -f "$OUT/summary.json.tmp" "$OUT/summary.json"
{ echo "status $(date -u +%FT%TZ): service $(systemctl is-active mkhalifa-meme-lab.service) · commit $(git -C "$D/repo" rev-parse --short HEAD)"
  journalctl -u mkhalifa-meme-lab.service -n 12 --no-pager 2>/dev/null | cut -c1-200
  [ -f "$D/data/check.txt" ] && cat "$D/data/check.txt"; } > "$OUT/install.log" 2>&1
chmod 644 "$OUT"/* 2>/dev/null || true
cd "$D/repo" || exit 1
git fetch -q origin main || exit 0
NEW=$(git rev-parse origin/main)
[ "$NEW" = "$(git rev-parse HEAD)" ] && exit 0
[ "$NEW" = "$(cat $D/failed 2>/dev/null)" ] && exit 0
rm -rf "$D/try" && git clone -q "$D/repo" "$D/try" && git -C "$D/try" checkout -q "$NEW" 2>/dev/null \
  || { git -C "$D/try" fetch -q "$D/repo" "$NEW" && git -C "$D/try" checkout -q FETCH_HEAD; }
if ! (cd "$D/try" && "$D/venv/bin/python" -m unittest discover -s tests -t . >/dev/null 2>"$D/test.log"); then
  echo "$NEW" > "$D/failed"; rm -rf "$D/try"; exit 1
fi
rm -rf "$D/try"
git reset -q --hard "$NEW"
"$D/venv/bin/pip" install -q -r requirements.txt
install -m 644 deploy/mkhalifa-meme-lab.service deploy/mkhalifa-meme-update.service deploy/mkhalifa-meme-update.timer /etc/systemd/system/
systemctl daemon-reload
systemctl restart mkhalifa-meme-lab.service
