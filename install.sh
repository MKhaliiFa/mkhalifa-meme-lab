#!/usr/bin/env bash
# One-time install on the Hetzner server (root). Safe to run again.
#   curl -fsSL https://raw.githubusercontent.com/MKhaliiFa/mkhalifa-meme-lab/main/install.sh | bash
# Everything lives in /opt/mkhalifa-meme-lab and runs as its own user (memelab), capped at 300 MB and 40 % CPU.
# The live trading bot is never touched: the lab only writes /opt/mkhalifa/data/meme/summary.json, which the
# bot's 09:00 daily report reads. No keys, no wallet, no money.
set -euo pipefail
D=/opt/mkhalifa-meme-lab
[ "$(id -u)" = 0 ] || { echo "Run as root"; exit 1; }
export DEBIAN_FRONTEND=noninteractive
echo "== meme lab install $(date -u +%FT%TZ)"
PYV=$(python3 -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
if ! python3 -m venv /tmp/meme-venv-test >/dev/null 2>&1; then     # Debian/Ubuntu: venv needs its own package
  apt-get update -qq && apt-get install -y -qq "python${PYV}-venv" python3-venv >/dev/null 2>&1 \
    || apt-get install -y -qq python3-venv >/dev/null
fi
rm -rf /tmp/meme-venv-test
command -v git >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }
id memelab >/dev/null 2>&1 || useradd --system --home-dir "$D" --no-create-home --shell /usr/sbin/nologin memelab
mkdir -p "$D/data" /opt/mkhalifa/data/meme
if [ -d "$D/repo/.git" ]; then
  git -C "$D/repo" fetch -q origin main && git -C "$D/repo" reset -q --hard origin/main
else
  git clone -q --depth 20 https://github.com/MKhaliiFa/mkhalifa-meme-lab.git "$D/repo"
fi
[ -x "$D/venv/bin/pip" ] || { rm -rf "$D/venv"; python3 -m venv "$D/venv"; }
"$D/venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
"$D/venv/bin/pip" install -q -r "$D/repo/requirements.txt"
chown -R memelab:memelab "$D/data" /opt/mkhalifa/data/meme
(cd "$D/repo" && "$D/venv/bin/python" -m unittest discover -s tests -t . 2>&1 | tail -2) || true
install -m 644 "$D/repo/deploy/mkhalifa-meme-lab.service" "$D/repo/deploy/mkhalifa-meme-update.service" \
  "$D/repo/deploy/mkhalifa-meme-update.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mkhalifa-meme-lab.service mkhalifa-meme-update.timer >/dev/null 2>&1
systemctl restart mkhalifa-meme-lab.service
echo "== source check"
runuser -u memelab -- bash -c "cd $D/repo && set -a && . ./config.env && set +a && $D/venv/bin/python -m memelab.main --check" \
  > "$D/data/check.txt" 2>&1 || true
cat "$D/data/check.txt"
echo "== lab: $(systemctl is-active mkhalifa-meme-lab.service) · live bot: $(docker inspect -f '{{.State.Status}}' mkhalifa-bot 2>/dev/null || echo none)"
