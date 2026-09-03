# Linux fundamentals

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

Everything here was run inside disposable Ubuntu containers, so no test user was ever created on my
laptop — and because macOS has neither `adduser`, `useradd`, nor `journalctl`, a real Linux
environment was needed anyway.

| Task | Script | Output |
| --- | --- | --- |
| 1 & 2 — links, users | [`linux-lab.sh`](linux-lab.sh) | [lab-output.txt](lab-output.txt) |
| 3 — journalctl | [`journalctl-lab.sh`](journalctl-lab.sh) | [journalctl-output.txt](journalctl-output.txt) |

```bash
docker run --rm -v "$PWD":/lab ubuntu:24.04 bash -c \
  'apt-get -qq update >/dev/null && apt-get -qq install -y file adduser perl >/dev/null; bash /lab/linux-lab.sh'
```

---

## Task 1 — soft links and hard links

A **hard link** is another directory entry pointing at the same inode. The file has two names and
no notion of which is "the original". A **soft (symbolic) link** is a small separate file whose
contents are a *path* to somewhere else.

```text
$ ls -li
2768363 -rw-r--r-- 2 root root 21 hard-link.txt
2768363 -rw-r--r-- 2 root root 21 original.txt
2768364 lrwxrwxrwx 1 root root 12 soft-link.txt -> original.txt
```

Three things in that output tell the whole story:

- `original.txt` and `hard-link.txt` show **inode 2768363** — one file, two names.
- Their **link count is 2** (third column). The symlink's is 1.
- The symlink has **its own inode**, type `l`, and is **12 bytes** — exactly the length of the
  string `original.txt`. That is all it stores.

### What happens when the original is deleted

```text
$ rm original.txt

$ cat hard-link.txt
the original content
appended through the hard link      <- still works

$ cat soft-link.txt
cat: soft-link.txt: No such file or directory
```

The hard link still works because the data belongs to the **inode**, and an inode is only freed
when its link count reaches zero. `rm` does not delete file contents — it removes a name and
decrements the count.

The symlink is now **dangling**: it is still a valid symlink, but its target is gone.

```text
$ test -L soft-link.txt && echo 'still a symlink'
still a symlink
$ test -e soft-link.txt || echo 'but its target does not exist'
but its target does not exist
```

`-L` tests the link itself, `-e` follows it. That distinction is how you detect a broken link.

### What a hard link cannot do

```text
$ ln /etc/hostname /tmp/link-lab/x
ln: failed to create hard link ... 'Invalid cross-device link'

$ ln /tmp /tmp/link-lab/dirlink
ln: /tmp: hard link not allowed for directory
```

Inode numbers are only unique **within one filesystem**, so a hard link can never cross a
filesystem boundary. Directories are refused because a hard-linked directory could create a cycle
in the tree that `..` could not resolve and that tools walking the filesystem could not escape.
A symlink does both without complaint, because it only stores a path string.

### Summary table

| | Hard link | Soft link |
| --- | --- | --- |
| Shares the target's inode | Yes | No — has its own |
| What it stores | nothing extra; another name | a path string |
| Size | same as the file | length of the path |
| Cross-filesystem | **No** | Yes |
| Point at a directory | **No** | Yes |
| Survives deleting the original | **Yes** | No — becomes dangling |
| Can dangle | No | Yes |
| Create | `ln target name` | `ln -s target name` |
| Identify | link count > 1 | `l` in `ls -l`, `-> target` |

### As an interview answer

A hard link is a second name for the same inode; a symlink is a small file containing a path.
Delete the original and the hard link still works because the inode survives while any name points
at it, while the symlink breaks because the path it stores no longer resolves. Hard links cannot
cross filesystems or point at directories, since inode numbers are only unique within a filesystem
and directory hard links would let cycles into the tree.

---

## Task 2 — `adduser` vs `useradd`

They are not two variants of the same tool. One calls the other:

```text
$ file $(command -v adduser) $(command -v useradd)
/usr/sbin/adduser: Perl script text executable
/usr/sbin/useradd: ELF 64-bit LSB pie executable, ARM aarch64 ...
```

`useradd` is a **compiled binary** from the `shadow` package — the low-level tool, present on every
Linux distribution. `adduser` is a **Perl script** that wraps it and applies Debian/Ubuntu policy.

### `useradd` with no options does the bare minimum

```text
$ useradd testuser-plain
$ getent passwd testuser-plain
testuser-plain:x:1001:1001::/home/testuser-plain:/bin/sh

$ ls -d /home/testuser-plain
ls: cannot access '/home/testuser-plain': No such file or directory
```

`/etc/passwd` records a home directory that **was never created**, and the shell is `/bin/sh`. That
is not a bug — `useradd` does exactly what it is told and nothing more, which is what you want in a
provisioning script. To get a usable account you have to ask:

```bash
useradd -m -s /bin/bash testuser-useradd    # -m makes the home dir, -s sets the shell
```

### `adduser` applies the distribution's defaults

```text
$ adduser --gecos '' --disabled-password testuser-adduser
info: Adding new group `testuser-adduser' (1003) ...
info: Adding new user `testuser-adduser' (1003) with group `testuser-adduser (1003)' ...
info: Creating home directory `/home/testuser-adduser' ...
info: Copying files from `/etc/skel' ...
info: Adding new user `testuser-adduser' to supplemental / extra groups `users' ...

$ ls -a /home/testuser-adduser
.  ..  .bash_logout  .bashrc  .profile
```

Home directory created, `/etc/skel` copied in, `/bin/bash` set, a matching user group made, and the
account added to `users` — all without being asked. Run interactively it also prompts for a
password and the GECOS fields.

| | `useradd` | `adduser` |
| --- | --- | --- |
| Type | compiled binary (`shadow`) | Perl wrapper script |
| Available on | every Linux distribution | Debian / Ubuntu family |
| Home directory | only with `-m` | always |
| Shell | `/etc/default/useradd`, often `/bin/sh` | `/bin/bash` |
| `/etc/skel` copied | only with `-m` | yes |
| User group | depends on config | always creates a matching one |
| Password prompt | no — needs `passwd` after | yes, interactively |
| Best for | scripts, automation, portability | a human at an Ubuntu terminal |

### Which is preferred on Ubuntu, and why

**`adduser`.** Ubuntu's own `useradd` man page says so directly. It is the policy-aware front end:
it produces an account that matches what the rest of the distribution expects — home directory,
skeleton files, correct shell, matching group — where bare `useradd` produces a half-configured
account that fails in confusing ways later.

The exception is **scripting**. `adduser` is interactive by default and is Debian-family only, so
Ansible, cloud-init, and Dockerfiles use `useradd -m -s /bin/bash` with explicit flags, which is
non-interactive, predictable, and portable.

### Cleanup

```bash
deluser --remove-home testuser-adduser   # the adduser-family counterpart
userdel -r testuser-useradd              # the useradd-family counterpart
```

Both test users were removed at the end of the run — the transcript ends with
`all test users removed`. Note that `deluser --remove-home` needs the `perl` package installed;
without it, it refuses.

---

## Task 3 — `journalctl`

### The obstacle, and how I got around it

`journalctl` reads the journal maintained by `systemd-journald`, which only exists if **systemd is
PID 1**. A normal container runs the application as PID 1:

```text
$ ps -p 1 -o pid,comm
    1 bash
$ command -v journalctl
journalctl is not installed
```

So rather than only describe the commands, I built a small Ubuntu image that genuinely boots
systemd, with nginx installed to give the lab a real service — [`systemd-image/Dockerfile`](systemd-image/Dockerfile):

```bash
docker build -t vibhuti-systemd ./systemd-image
docker run -d --name systemd-lab --privileged --cgroupns=host \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw vibhuti-systemd
docker exec systemd-lab bash /journalctl-lab.sh
```

```text
$ ps -p 1 -o pid,comm
    1 systemd
$ systemctl is-system-running
running
```

`--privileged` and the cgroup mount are what systemd needs to manage cgroups inside a container.
That is fine for a throwaway lab; it is not something to do with a real workload.

### What journalctl is for

`systemd-journald` collects records from the kernel, from early boot, from every unit's
stdout/stderr, and from anything using syslog, and stores them as **indexed binary records**.
Each record carries structured metadata, which is the real advantage over tailing text files:

```text
$ journalctl -u nginx -o json-pretty -n 1
"_COMM"          : "systemd",
"_SYSTEMD_UNIT"  : "init.scope",
"_PID"           : "1",
"PRIORITY"       : "6",
"MESSAGE"        : "Started nginx.service - A high performance web server ..."
```

Because `_SYSTEMD_UNIT` and `PRIORITY` are fields rather than text, `-u` and `-p` are exact filters
rather than greps that might match the wrong line.

### Logs for a specific service

```text
$ journalctl -u nginx --no-pager
Sep 03 13:24:07 systemd[1]: Starting nginx.service ...
Sep 03 13:24:07 systemd[1]: Started nginx.service ...
```

After `systemctl restart nginx`, the stop and start both appear:

```text
$ journalctl -u nginx --since '1 minute ago'
... Stopping nginx.service ...
... nginx.service: Deactivated successfully.
... Stopped nginx.service ...
... Starting nginx.service ...
... Started nginx.service ...
```

### Finding a failure

I added a service that deliberately exits 3:

```text
$ journalctl -u broken.service --no-pager
systemd[1]: Starting broken.service ...
sh[160]: about to fail on purpose                                  <- the service's own stdout
systemd[1]: broken.service: Main process exited, code=exited, status=3/NOTIMPLEMENTED
systemd[1]: broken.service: Failed with result 'exit-code'.
systemd[1]: Failed to start broken.service ...
```

The service's own output **and** the exit code are both in the journal, with no log file to hunt
for. And when you do not yet know which service broke:

```text
$ journalctl -p err --no-pager
systemd[1]: Failed to start broken.service ...

$ systemctl --failed
● broken.service   loaded failed failed
```

### Housekeeping

```text
$ journalctl --disk-usage
Archived and active journals take up 8.0M in the file system.

$ journalctl --list-boots
IDX BOOT ID                          FIRST ENTRY                 LAST ENTRY
  0 aa769517b3e347f8...              Thu 2026-09-03 13:24:07 UTC Thu 2026-09-03 13:24:58 UTC
```

### The commands worth remembering

| Command | What it does |
| --- | --- |
| `journalctl` | everything, oldest first |
| `journalctl -n 20` | last 20 entries |
| `journalctl -f` | follow live, like `tail -f` |
| `journalctl -b` / `-b -1` | this boot / the previous boot |
| `journalctl -u nginx` | one unit |
| `journalctl -u nginx -f` | one unit, live — the everyday one |
| `journalctl -p err` | priority `err` (3) and worse |
| `journalctl --since "1 hour ago"` | time window |
| `journalctl --since today --until "10:00"` | a bounded window |
| `journalctl -k` | kernel messages only |
| `journalctl -xeu nginx` | last entries for a unit, with explanations |
| `journalctl -o json-pretty` | structured output |
| `journalctl --disk-usage` | space used |
| `journalctl --vacuum-time=7d` | delete records older than 7 days |

Priorities run 0 `emerg`, 1 `alert`, 2 `crit`, 3 `err`, 4 `warning`, 5 `notice`, 6 `info`,
7 `debug`. `-p` is inclusive of everything more severe, so `-p warning` also shows errors.

In containers there is no journal, so the equivalent is `docker logs <container>`, which reads the
application's stdout/stderr — the reason containerised apps are expected to log to stdout rather
than to files.

---

## Task 4 — command cheat sheet

Reference material is in the session repository:
[`session2-linux`](https://github.com/Nency-Ravaliya/devops-heros/tree/main/session2-linux)
(`basic-linux.pdf`, `ad-linux.pdf`, `Linux Networking Cheat Sheet.pdf`).

| Purpose | Command |
| --- | --- |
| Where am I | `pwd` |
| List, including hidden, with inodes | `ls -la`, `ls -li` |
| Move around | `cd`, `cd -` (previous directory) |
| Create / copy / move / delete | `mkdir -p`, `cp -r`, `mv`, `rm -r` |
| Links | `ln target name`, `ln -s target name` |
| Read files | `cat`, `less`, `head -n`, `tail -n`, `tail -f` |
| Search **in** files | `grep -rn "pattern" .` |
| Search **for** files | `find . -name '*.log' -mtime -7` |
| File type and metadata | `file`, `stat` |
| Permissions and ownership | `chmod 644`, `chmod +x`, `chown user:group` |
| Disk space / directory sizes | `df -h`, `du -sh *` |
| Memory | `free -h` |
| Processes | `ps aux`, `ps -ef`, `top`, `htop` |
| Kill | `kill PID`, `kill -9 PID`, `pkill name` |
| Who am I | `whoami`, `id`, `groups` |
| Users | `adduser`, `useradd -m -s /bin/bash`, `passwd`, `deluser`, `userdel -r` |
| Switch user / elevate | `su - user`, `sudo -i` |
| Interfaces and routes | `ip addr`, `ip route` |
| Listening sockets | `ss -tulpn` |
| Services | `systemctl status/start/stop/restart/enable` |
| Logs | `journalctl -u <unit> -f`, `journalctl -p err` |
| Archives | `tar -czf out.tar.gz dir/`, `tar -xzf out.tar.gz` |
| Download | `curl -O url`, `wget url` |
| Help | `man cmd`, `cmd --help`, `type cmd` |

Two habits worth keeping: `ls -li` when links are involved, because the inode column answers the
hard-vs-soft question instantly; and `ss -tulpn` before assuming a service is unreachable, because
it shows whether the process is bound to `0.0.0.0` or only to `127.0.0.1`.
