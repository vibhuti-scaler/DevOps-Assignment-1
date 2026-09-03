#!/usr/bin/env bash
#
# Networking command practice.
#
# Runs the checks in the order I would actually use them when something is
# broken: start at the machine and work outwards.
#
#   interface -> address -> route -> DNS -> remote port -> application
#
# Prefers the modern Linux tools (ip, ss) and falls back to the BSD ones
# (ifconfig, netstat) so it also runs on macOS.

set -uo pipefail

have() { command -v "$1" >/dev/null 2>&1; }
step() { printf '\n$ %s\n' "$*"; "$@" 2>&1; }

echo "=============================================================="
echo "1. Who am I?"
echo "=============================================================="
step hostname

echo
echo "=============================================================="
echo "2. Interfaces and addresses"
echo "=============================================================="
if have ip; then
    step ip -brief address
else
    step ifconfig -a
fi

echo
echo "=============================================================="
echo "3. Routing table - how packets leave this machine"
echo "=============================================================="
if have ip; then
    step ip route
else
    step netstat -rn -f inet
fi

echo
echo "=============================================================="
echo "4. DNS - can a name be turned into an address?"
echo "=============================================================="
step nslookup example.com
if have dig; then
    echo
    step dig +short example.com A
fi

echo
echo "=============================================================="
echo "5. IP connectivity, bypassing DNS entirely"
echo "=============================================================="
step ping -c 3 1.1.1.1

echo
echo "=============================================================="
echo "6. Path to a remote host"
echo "=============================================================="
if have traceroute; then
    step traceroute -m 8 -w 2 1.1.1.1
else
    echo "traceroute not installed on this system"
fi

echo
echo "=============================================================="
echo "7. The full application path - DNS, TCP, TLS, HTTP"
echo "=============================================================="
step curl -sS -I https://example.com

echo
echo "Timing breakdown of the same request:"
printf '\n$ curl -sS -o /dev/null -w ... https://example.com\n'
curl -sS -o /dev/null -w \
'  dns lookup   : %{time_namelookup}s
  tcp connect  : %{time_connect}s
  tls handshake: %{time_appconnect}s
  first byte   : %{time_starttransfer}s
  total        : %{time_total}s
  http code    : %{http_code}
' https://example.com

echo
echo "=============================================================="
echo "8. Listening sockets on this machine"
echo "=============================================================="
if have ss; then
    step ss -tuln
else
    step netstat -an -p tcp
fi

echo
echo "=============================================================="
echo "9. Is a specific remote port open?"
echo "=============================================================="
if have nc; then
    step nc -z -v -w 3 example.com 443
else
    echo "nc not installed on this system"
fi
