#!/bin/bash
# Map a Windows share (office Z:) onto /mnt/fh6parse-cad, read-only.
# Plug the Pi into the company network; the share mounts on first use.
#
# On a Windows PC, find the UNC for Z:
#   net use Z:
# Example: Z: is \\fileserver\Dokumentacja  →  //fileserver/Dokumentacja
#
# Guest share:
#   sudo bash packaging/connect-windows-share.sh //fileserver/Dokumentacja --guest
# Domain account:
#   sudo bash packaging/connect-windows-share.sh //fileserver/Dokumentacja --user kiosk --domain COMPANY

set -euo pipefail

MOUNTPOINT=/mnt/fh6parse-cad
CRED=/etc/fh6parse-cad.cred
FSTAB=/etc/fstab
INI=/etc/fh6parse-kiosk.ini
UNC=""
USER_NAME=""
DOMAIN=""
GUEST=0

usage() {
  echo "Usage: sudo bash $0 //SERVER/Share [--guest | --user NAME --domain DOMAIN]"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --guest) GUEST=1; shift ;;
    --user) USER_NAME="${2:-}"; shift 2 ;;
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    //*) UNC="$1"; shift ;;
    *) echo "Unknown argument: $1"; usage ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo)."
  exit 1
fi
if [ -z "$UNC" ]; then
  usage
fi
if [ "$GUEST" -eq 0 ] && [ -z "$USER_NAME" ]; then
  echo "Need --guest or --user NAME (and usually --domain)."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get install -y cifs-utils >/dev/null
mkdir -p "$MOUNTPOINT"
chown kiosk:kiosk "$MOUNTPOINT" 2>/dev/null || true
chmod 755 "$MOUNTPOINT"

OPTS="ro,uid=kiosk,gid=kiosk,iocharset=utf8,file_mode=0444,dir_mode=0555,_netdev,nofail,x-systemd.automount,x-systemd.idle-timeout=600"
if [ "$GUEST" -eq 1 ]; then
  OPTS="guest,${OPTS}"
else
  umask_old=$(umask)
  umask 077
  {
    echo "username=${USER_NAME}"
    echo "password="
    if [ -n "$DOMAIN" ]; then
      echo "domain=${DOMAIN}"
    fi
  } > "$CRED"
  umask "$umask_old"
  chown root:root "$CRED"
  chmod 600 "$CRED"
  echo "Edit $CRED and put the account password on the password= line, then:"
  echo "  sudo chmod 600 $CRED"
  OPTS="credentials=${CRED},${OPTS}"
fi

MARKER="# fh6parse company CAD (read-only Windows share)"
if grep -qF "$MOUNTPOINT" "$FSTAB"; then
  echo "fstab already has $MOUNTPOINT — not changing it."
else
  printf '\n%s\n%s %s cifs %s 0 0\n' "$MARKER" "$UNC" "$MOUNTPOINT" "$OPTS" >> "$FSTAB"
fi

systemctl daemon-reload
if [ "$GUEST" -eq 1 ] || grep -q '^password=.\+' "$CRED" 2>/dev/null; then
  mount "$MOUNTPOINT" || echo "Mount will retry when the network is up (plug the Ethernet cable)."
else
  echo "Password still empty in $CRED — fill it in, then: sudo mount $MOUNTPOINT"
fi

if [ -f "$INI" ] && ! grep -q '^[[:space:]]*model_roots' "$INI"; then
  printf '\n# Read-only company STEP / docs (Windows Z:). Never written by fh6parse.\nmodel_roots = %s\n' "$MOUNTPOINT" >> "$INI"
  echo "Added model_roots = $MOUNTPOINT to $INI"
else
  echo "Set model_roots = $MOUNTPOINT in $INI if it is not already there."
fi

echo "Share is read-only (CIFS ro). fh6parse only reads .stp/.step; bitmaps go to /tmp/fh6parse-models."
echo "Done. Plug the Pi into the company network; the kiosk indexes the share in the background."
