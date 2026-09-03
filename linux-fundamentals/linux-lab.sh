#!/usr/bin/env bash
#
# Linux fundamentals - links and user management.
# Meant to be run inside a disposable Ubuntu container.

set -uo pipefail
step() { printf '\n$ %s\n' "$*"; "$@" 2>&1; }

echo "=============================================================="
echo "TASK 1 - soft links and hard links"
echo "=============================================================="

rm -rf /tmp/link-lab && mkdir -p /tmp/link-lab && cd /tmp/link-lab
printf 'the original content\n' > original.txt

step ln    original.txt hard-link.txt      # hard link
step ln -s original.txt soft-link.txt      # soft (symbolic) link

echo
echo "\$ ls -li"
ls -li
echo
echo "The first column is the inode number."
echo "  original.txt and hard-link.txt share ONE inode - they are two names"
echo "  for the same file, and the link count (column 3) is 2."
echo "  soft-link.txt has its own inode, type 'l', and displays -> original.txt."

echo
echo "\$ stat -c '%n  inode=%i  links=%h  size=%s  type=%F' original.txt hard-link.txt soft-link.txt"
stat -c '%n  inode=%i  links=%h  size=%s  type=%F' original.txt hard-link.txt soft-link.txt
echo
echo "The soft link is only 12 bytes - just the length of the path it stores."

echo
echo "--- Writing through either name changes the same data ---"
printf 'appended through the hard link\n' >> hard-link.txt
step cat original.txt

echo
echo "--- Now delete the original ---"
step rm original.txt
echo
echo "\$ ls -li"
ls -li
echo
echo "\$ cat hard-link.txt"
cat hard-link.txt
echo "  The hard link still works. The data lives with the inode, and the inode"
echo "  is only freed when its link count reaches zero."
echo
echo "\$ cat soft-link.txt"
cat soft-link.txt 2>&1
echo "  The soft link is now dangling - it still stores the path 'original.txt',"
echo "  but nothing is there any more."
echo
echo "\$ test -L soft-link.txt && echo 'still a symlink'; test -e soft-link.txt || echo 'but its target does not exist'"
test -L soft-link.txt && echo "still a symlink"
test -e soft-link.txt || echo "but its target does not exist"

echo
echo "--- What a hard link cannot do ---"
echo "\$ ln /etc/hostname /tmp/link-lab/x   # different filesystems"
ln /etc/hostname /tmp/link-lab/x 2>&1 || true
echo "\$ ln /tmp /tmp/link-lab/dirlink      # a directory"
ln /tmp /tmp/link-lab/dirlink 2>&1 || true
echo "  A symlink can do both of these without complaint."
step ln -s /tmp /tmp/link-lab/dirlink
step ls -ld /tmp/link-lab/dirlink

echo
echo "--- Deleting links ---"
step rm soft-link.txt
step rm hard-link.txt
echo "  Plain rm removes the name. The data goes only when the last name goes."
cd / && rm -rf /tmp/link-lab

echo
echo
echo "=============================================================="
echo "TASK 2 - adduser vs useradd"
echo "=============================================================="

echo
echo "\$ file \$(command -v adduser) \$(command -v useradd)"
file "$(command -v adduser)" "$(command -v useradd)"
echo
echo "useradd is a compiled binary from the shadow package - the low-level tool."
echo "adduser is a Perl script that wraps it and applies Debian/Ubuntu policy."

echo
echo "--- useradd on its own, with no options ---"
step useradd testuser-plain
step getent passwd testuser-plain
echo
echo "\$ ls -d /home/testuser-plain"
ls -d /home/testuser-plain 2>&1
echo "  No home directory, and the shell is /bin/sh. useradd does exactly what"
echo "  it is told and nothing more, which is what you want in a script."

echo
echo "--- The same thing done properly with useradd ---"
step useradd -m -s /bin/bash testuser-useradd
step getent passwd testuser-useradd
step ls -ld /home/testuser-useradd

echo
echo "--- adduser, the recommended command on Ubuntu ---"
echo "\$ adduser --gecos '' --disabled-password testuser-adduser"
adduser --gecos '' --disabled-password testuser-adduser 2>&1
echo
step getent passwd testuser-adduser
step ls -ld /home/testuser-adduser
step id testuser-adduser
echo
echo "\$ ls -a /home/testuser-adduser"
ls -a /home/testuser-adduser
echo "  adduser created the home directory, copied the skeleton files from"
echo "  /etc/skel, set /bin/bash, and made a matching user group - all by"
echo "  default. Run without --disabled-password it also prompts for one."

echo
echo "--- Removing the test users ---"
step deluser --remove-home testuser-adduser
step userdel -r testuser-useradd
step userdel testuser-plain
echo
echo "\$ getent passwd | grep testuser || echo 'all test users removed'"
getent passwd | grep testuser || echo "all test users removed"

echo
echo
echo "=============================================================="
echo "TASK 3 - journalctl in this environment"
echo "=============================================================="
echo "\$ command -v journalctl || echo 'journalctl is not installed'"
command -v journalctl || echo "journalctl is not installed"
echo
echo "\$ ps -p 1 -o pid,comm"
ps -p 1 -o pid,comm
echo
echo "PID 1 is not systemd, so there is no journal to read here."
echo "journalctl is demonstrated separately - see systemd-journal-output.txt."
