# Networking command practice

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

[`network-checks.sh`](network-checks.sh) runs the commands in the order I would actually use them
when something is broken — start at the machine and work outwards:

```text
interface  ->  address  ->  route  ->  DNS  ->  remote port  ->  application
```

That order matters. Each step only makes sense if the one before it worked, so the first failure
tells you which layer to look at instead of guessing.

Full output: [command-output.txt](command-output.txt). It was captured inside a disposable
`nicolaka/netshoot` container, so the addresses belong to the lab rather than to my home network.
The script prefers the modern Linux tools (`ip`, `ss`) and falls back to the BSD ones (`ifconfig`,
`netstat`) so it also runs on macOS.

## The commands and what each one told me

| # | Command | What it checks | What I saw |
| --- | --- | --- | --- |
| 1 | `hostname` | which machine I am on | `09909ca17a42` — a container ID, confirming I am in the lab |
| 2 | `ip -brief address` | interfaces, state, addresses | `lo` up, `eth0@if173` up with `172.17.0.3/16` |
| 3 | `ip route` | how packets leave | `default via 172.17.0.1 dev eth0` |
| 4 | `nslookup` / `dig +short` | name → address | `example.com` → `172.66.147.243`, `104.20.23.154` |
| 5 | `ping -c 3 1.1.1.1` | raw IP reachability | 0% loss, avg 20.4 ms |
| 6 | `traceroute` | the path taken | hop 1 is the Docker gateway, then all `*` |
| 7 | `curl -I https://example.com` | DNS + TCP + TLS + HTTP together | `HTTP/2 200` |
| 8 | `ss -tuln` | what is listening locally | nothing |
| 9 | `nc -z -v example.com 443` | one specific remote port | `succeeded!` |

## What I understood from each

**`hostname`** — the machine's own name. Inside a container it defaults to the short container ID,
which is a quick way to confirm which environment a shell is really in.

**`ip -brief address`** — every interface, whether it is UP, and what address it holds. `lo` is
loopback and always exists. The interesting one is `eth0@if173`: the `@if173` suffix means it is one
end of a **veth pair**, and its partner is interface 173 on the Docker host. That is exactly the
bridge-mode plumbing from [Task 1 of the Docker networking homework](../docker-networking/). The
`/16` says the container's subnet is `172.17.0.0/16`, which is `docker0`'s default range.

**`ip route`** — having an address is not enough; the machine also needs to know where to send
traffic that is not local. The `default via 172.17.0.1` line is the gateway, and `172.17.0.1` is
`docker0` on the host. The second line is the on-link route: anything in `172.17.0.0/16` is a
neighbour and needs no gateway.

**`nslookup` and `dig`** — name resolution on its own. The reply came from `192.168.65.7`, Docker's
internal resolver, not from my router. `dig +short` gives just the answer, which is what you want in
a script; `nslookup` shows the server it asked, which is what you want when you suspect the wrong
resolver is being used. Two addresses came back, so the name is served by more than one edge node.

**`ping -c 3 1.1.1.1`** — deliberately an IP, not a name, so it tests connectivity **without** DNS.
Running this before `nslookup` is the quickest way to separate a routing problem from a DNS
problem: if the ping works but the name does not resolve, the network is fine and DNS is broken.

**`traceroute`** — hop 1 was the Docker gateway and everything after that was `*`. That is not a
fault: Docker Desktop's VM does not return the ICMP time-exceeded messages traceroute relies on, and
plenty of routers on the public internet drop them too. It is a good reminder that `*` means "no
reply to this probe", not "the packet stopped here" — the `curl` in step 7 proves traffic reaches
the internet perfectly well.

**`curl -I`** — the only check that exercises the whole stack at once: resolve the name, open TCP,
complete the TLS handshake, send an HTTP request. `-I` asks for headers only. `HTTP/2 200` means
every layer beneath it worked. The `-w` timing breakdown then says *where* the time went:

```text
dns lookup   : 0.002075s
tcp connect  : 0.017150s   <- 15 ms of TCP setup
tls handshake: 0.044658s   <- 27 ms of TLS on top
first byte   : 0.062588s
total        : 0.062656s
```

Each figure is cumulative, so the gaps are the costs. When a page feels slow, this immediately says
whether it is DNS, the network round trip, TLS, or the server thinking.

**`ss -tuln`** — sockets **listening on this machine**. It came back empty, which is correct for a
container that only runs a shell. On a server this is how you confirm a service is actually bound,
and to which address: `0.0.0.0:80` accepts from anywhere, `127.0.0.1:80` only from the machine
itself — a very common reason a service "is running" but nothing can reach it. The flags are
`-t` TCP, `-u` UDP, `-l` listening only, `-n` numeric (skip the DNS lookups that make it slow).

**`nc -z -v host 443`** — tests one specific TCP port without sending data. `-z` means just check.
Useful when `ping` fails because ICMP is blocked but the service itself is fine, and for checking
firewall rules from the outside.

## The order in practice

`ping` failing does not mean the network is down — many hosts drop ICMP on purpose. If ping fails I
go to `curl` or `nc` against the real port before concluding anything, because those test the path
the application will actually use.

The reverse is also true: an interface with an address proves nothing on its own. It also needs a
route, DNS has to resolve, the remote port has to be open, and the service behind it has to answer.
Working outwards in that order finds the broken layer in a few commands instead of guessing.

## Task 1 — session repository

The [`session4-networking`](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session4-networking)
folder covers IP addressing and subnetting. The parts worth writing down:

| Class | First octet | Default mask | Network bits | Host bits |
| --- | --- | --- | ---: | ---: |
| A | 1–127 | `255.0.0.0` (`/8`) | 8 | 24 |
| B | 128–191 | `255.255.0.0` (`/16`) | 16 | 16 |
| C | 192–223 | `255.255.255.0` (`/24`) | 24 | 8 |
| D | 224–239 | multicast | — | — |

Usable hosts on a network is `2^(host bits) − 2` — the all-zeros address is the network itself and
the all-ones address is the broadcast, so neither can be assigned. A `/24` therefore gives
`2^8 − 2 = 254` usable addresses, and a `/8` gives `2^24 − 2 = 16,777,214`.

The private ranges, which never appear on the public internet:

```text
10.0.0.0     - 10.255.255.255    (10.0.0.0/8)
172.16.0.0   - 172.31.255.255    (172.16.0.0/12)
192.168.0.0  - 192.168.255.255   (192.168.0.0/16)
```

This connects directly back to the output above: the container sat on `172.17.0.3/16`, inside
`172.16.0.0/12`. Docker deliberately allocates its bridge networks from private space, which is why
container addresses are only meaningful on their own host — and why crossing hosts needs the
[overlay network](../docker-networking/overlay-network.md) from the Docker networking homework.
