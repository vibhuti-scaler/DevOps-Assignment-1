#!/usr/bin/env bash
#
# System information script
#
# Covers every item the homework asks for:
#   date, hostname, username, disk usage, running processes,
#   variables, read -p, mkdir, touch, and > output redirection.

set -euo pipefail

# ---------------------------------------------------------------
# Variables holding the system details
# ---------------------------------------------------------------
current_date=$(date '+%A, %d %B %Y, %H:%M:%S %Z')
host_name=$(hostname)
current_user=$(whoami)

report_dir="system-report"
process_file="$report_dir/processes.txt"
summary_file="$report_dir/summary.txt"

# ---------------------------------------------------------------
# Take input from the user with read -p
# ---------------------------------------------------------------
read -r -p "Enter your name: "          student_name
read -r -p "Enter your roll number: "   roll_no
read -r -p "Enter your batch: "         batch
read -r -p "Enter a short comment: "    comment

# ---------------------------------------------------------------
# Create the directory and the files
# ---------------------------------------------------------------
mkdir -p "$report_dir"
touch "$process_file" "$summary_file"

# ---------------------------------------------------------------
# Store the running processes in a file with > output redirection
# ---------------------------------------------------------------
ps -eo pid,ppid,user,%cpu,%mem,comm > "$process_file"
process_count=$(($(wc -l < "$process_file") - 1))

# GNU ps supports --sort; the BSD ps on macOS does not, so fall back.
top_by_memory=$(ps -eo pid,user,%mem,comm --sort=-%mem 2>/dev/null \
    || ps -eo pid,user,%mem,comm)

# ---------------------------------------------------------------
# Build the report. tee writes it to the file and the screen at once.
# ---------------------------------------------------------------
{
    echo "=================================================="
    echo "            SYSTEM INFORMATION REPORT"
    echo "=================================================="
    echo
    echo "Name        : $student_name"
    echo "Roll number : $roll_no"
    echo "Batch       : $batch"
    echo "Comment     : $comment"
    echo
    echo "--------------------------------------------------"
    echo "Date        : $current_date"
    echo "Hostname    : $host_name"
    echo "Username    : $current_user"
    echo "--------------------------------------------------"
    echo
    echo "Disk usage:"
    df -h
    echo
    echo "Running processes: $process_count"
    echo "Full list written to $process_file using > redirection."
    echo
    echo "Top 10 processes by memory:"
    # sed -n rather than head, so the producer is never killed by SIGPIPE
    # when the reader closes the pipe early (which trips `set -o pipefail`).
    printf '%s\n' "$top_by_memory" | sed -n '1,11p'
} | tee "$summary_file"

echo
echo "First 10 lines of $process_file:"
sed -n '1,10p' "$process_file"

echo
echo "Files created:"
ls -l "$report_dir"
