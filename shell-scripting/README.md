# Shell scripting — system information script

- **Name:** Vibhuti Bhatnagar · **Roll no:** 24BCS10288 · **Batch:** B

[`system-info.sh`](system-info.sh) collects the system details the homework asks for, prompts for
the student's details, and writes the process list to a generated file.

## Requirements and where each one is met

| Requirement | In the script |
| --- | --- |
| Prints the current date | `current_date=$(date '+%A, %d %B %Y, %H:%M:%S %Z')` |
| Prints the hostname | `host_name=$(hostname)` |
| Prints the username | `current_user=$(whoami)` |
| Prints the disk usage | `df -h` |
| Prints the running processes | `ps -eo pid,ppid,user,%cpu,%mem,comm` |
| Uses variables | `current_date`, `host_name`, `current_user`, `report_dir`, `process_file`, `summary_file`, `process_count` |
| Takes user input with `read -p` | four prompts: name, roll number, batch, comment |
| Creates a directory with `mkdir` | `mkdir -p "$report_dir"` |
| Creates a file with `touch` | `touch "$process_file" "$summary_file"` |
| Stores processes with `>` redirection | `ps -eo ... > "$process_file"` |

The name / roll number / comment prompts come from the session repository's
[`task.md`](https://github.com/Nency-Ravaliya/devops-heros/blob/main/session3-shell-scripting/task.md),
which asks for those on top of the items in the homework document.

## Run it

```bash
chmod +x system-info.sh
./system-info.sh
```

It prompts for four values, then prints the report and writes two files into `system-report/`:

```text
system-report/
├── processes.txt   # full process list, written with > redirection
└── summary.txt     # the report, written with tee
```

`system-report/` is in [`.gitignore`](../.gitignore) — it is regenerated on every run and its
contents are specific to the machine it ran on.

## Sample run

[sample-output.txt](sample-output.txt) holds a complete run inside a disposable `ubuntu:24.04`
container, so the hostname and process list belong to the lab and not to my laptop. The four
`read -p` prompts were answered from a here-document to make the run reproducible:

```bash
docker run --rm -i -v "$PWD":/lab -w /lab ubuntu:24.04 bash -c '
  bash system-info.sh <<INPUT
Vibhuti Bhatnagar
24BCS10288
B
DevOps homework - shell scripting task
INPUT
'
```

The same file also shows the script running on the macOS host, to confirm it is portable.

## Two things I had to handle

**`ps --sort` is GNU-only.** The BSD `ps` on macOS rejects `--sort=-%mem`, so the script tries the
GNU form and falls back:

```bash
top_by_memory=$(ps -eo pid,user,%mem,comm --sort=-%mem 2>/dev/null \
    || ps -eo pid,user,%mem,comm)
```

**`head` in a pipeline breaks `set -o pipefail`.** `ps | head -11` makes `head` close the pipe as
soon as it has 11 lines, `ps` is killed by SIGPIPE, and the script exits 141 despite having worked.
Using `sed -n '1,11p'` instead reads all the input, so the producer is never killed. That was the
difference between the script exiting 141 and exiting 0 on macOS.

The script also runs under `set -euo pipefail` and quotes every variable expansion, so a path with
spaces — which this repository has — does not split into separate arguments.
