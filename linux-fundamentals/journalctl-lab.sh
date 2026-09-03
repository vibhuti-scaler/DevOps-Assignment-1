#!/usr/bin/env bash
#
# Task 3 - journalctl, run inside a container that really does boot systemd,
# so the journal exists and there is a service to inspect.

set -uo pipefail
step() { printf '\n$ %s\n' "$*"; "$@" 2>&1; }

echo "=============================================================="
echo "0. This really is systemd"
echo "=============================================================="
step ps -p 1 -o pid,comm
step systemctl is-system-running
step systemd-analyze

echo
echo "=============================================================="
echo "1. What journalctl is"
echo "=============================================================="
echo "systemd-journald collects log records from the kernel, from early boot,"
echo "from every unit's stdout/stderr, and from anything using syslog. It stores"
echo "them as indexed binary records, and journalctl is how you read them back."
echo "The win over tailing files in /var/log is that every record carries"
echo "structured metadata - unit, PID, UID, priority, boot ID, timestamp - so"
echo "you can filter instead of grepping."

echo
echo "\$ journalctl --no-pager | wc -l   # total records available"
journalctl --no-pager | wc -l

echo
echo "=============================================================="
echo "2. System logs"
echo "=============================================================="
echo "\$ journalctl -n 10 --no-pager     # the 10 most recent entries"
journalctl -n 10 --no-pager

echo
echo "\$ journalctl -b --no-pager | head -12   # this boot, from the beginning"
journalctl -b --no-pager | head -12

echo
echo "=============================================================="
echo "3. Logs for one specific service"
echo "=============================================================="
step systemctl status nginx --no-pager

echo
echo "\$ journalctl -u nginx --no-pager"
journalctl -u nginx --no-pager

echo
echo "--- Restart it and watch new records appear ---"
step systemctl restart nginx
sleep 2
echo "\$ journalctl -u nginx --no-pager --since '1 minute ago'"
journalctl -u nginx --no-pager --since "1 minute ago"

echo
echo "=============================================================="
echo "4. Filtering"
echo "=============================================================="
echo "\$ journalctl -u nginx -o json-pretty --no-pager -n 1"
journalctl -u nginx -o json-pretty --no-pager -n 1 \
    | grep -E '"(MESSAGE|_SYSTEMD_UNIT|PRIORITY|_PID|_COMM)"'
echo
echo "Those fields are what makes -u, -p and the rest possible: each record is"
echo "structured, not a line of text."

echo
echo "--- A service that fails, so there is a real error to find ---"
cat > /etc/systemd/system/broken.service <<'UNIT'
[Unit]
Description=A deliberately broken service for the journalctl lab

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo "about to fail on purpose"; exit 3'
UNIT
systemctl daemon-reload
step systemctl start broken.service
echo
echo "\$ journalctl -u broken.service --no-pager"
journalctl -u broken.service --no-pager
echo
echo "The exit code and the service's own output are both in the journal,"
echo "with no log file to go looking for."

echo
echo "--- Filtering by priority now finds it without knowing the unit name ---"
echo "\$ journalctl -p err --no-pager"
journalctl -p err --no-pager
echo
echo "-p err shows priority 3 and worse. That is how you find what broke when"
echo "you do not already know which service to look at."
echo
echo "\$ systemctl --failed --no-pager"
systemctl --failed --no-pager

echo
echo "=============================================================="
echo "5. Housekeeping"
echo "=============================================================="
step journalctl --disk-usage
step journalctl --list-boots --no-pager

echo
echo "=============================================================="
echo "6. The commands worth remembering"
echo "=============================================================="
cat <<'TABLE'
  journalctl                        everything, oldest first
  journalctl -n 20                  last 20 entries
  journalctl -f                     follow live, like tail -f
  journalctl -b                     this boot only
  journalctl -b -1                  the previous boot
  journalctl -u nginx               one unit
  journalctl -u nginx -f            one unit, live
  journalctl -p err                 priority err and above
  journalctl --since "1 hour ago"   time window
  journalctl --since today --until "10:00"
  journalctl -k                     kernel messages only
  journalctl -o json-pretty         structured output
  journalctl --disk-usage           how much space the journal uses
  journalctl --vacuum-time=7d       delete records older than 7 days
TABLE
