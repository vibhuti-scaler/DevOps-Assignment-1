# A minimal Ubuntu image that actually boots systemd, so journalctl has a
# journal to read. A normal container runs the application as PID 1 and has
# no journal at all.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        systemd systemd-sysv nginx dbus && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# nginx gives the lab a real service whose logs can be inspected.
RUN systemctl enable nginx

# systemd expects SIGRTMIN+3 to shut down cleanly.
STOPSIGNAL SIGRTMIN+3

CMD ["/sbin/init"]
