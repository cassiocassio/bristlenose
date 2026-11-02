#!/usr/bin/env bash
# Run the reachability probe in whatever network state you are in, and save the result.
#
#   ./run.sh <label> [--with-stub] [--azure-host <resource>.openai.azure.com] [--timeout 5]
#
#   label        names the state: wifi-off, wan-unplugged, hotspot-no-data, portal, vpn-up,
#                vpn-dropped, dns-sinkhole, tls-intercept, clock-wrong, baseline ...
#   --sandboxed  run the App-Sandboxed build (network.client only); --sandboxed-ats adds an ATS
#                exception for captive.apple.com. Needs swiftc + codesign; see sandbox/build.sh.
#   --with-stub  also start stub_provider.py on loopback and probe every canned reply, plus the
#                local failure cases (no such host, refused port, black-holed address, plain
#                HTTP answering an https URL, a self-signed certificate). Needs python3 and
#                openssl; touches nothing outside this directory and a temp dir.
#
# Writes results/<label>-<UTC timestamp>.json and prints a one-line summary per request.
# Keyless: sends no API key and no user data. Does not change any system setting.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
label="${1:-}"; [ -n "$label" ] || { echo "usage: $0 <label> [--with-stub] [--azure-host H] [--timeout N]" >&2; exit 2; }
shift
with_stub=0; extra=(); variant=""
while [ $# -gt 0 ]; do
  case "$1" in
    --with-stub) with_stub=1 ;;
    --sandboxed) variant="-sbx" ;;
    --sandboxed-ats) variant="-sbx-ats" ;;
    --azure-host) extra+=(--azure-host "$2"); shift ;;
    --timeout) extra+=(--timeout "$2"); shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done

bin="$here/.build/probe${variant}"
if [ -n "$variant" ]; then
  [ -x "$bin" ] && [ "$here/probe.swift" -ot "$bin" ] || "$here/sandbox/build.sh" >&2 || exit 1
elif [ ! -x "$bin" ] || [ "$here/probe.swift" -nt "$bin" ]; then
  mkdir -p "$here/.build"
  swiftc -O -swift-version 5 "$here/probe.swift" -o "$bin" || { echo "swiftc failed" >&2; exit 1; }
fi

stub_pid=""; tmp=""
cleanup() { [ -n "$stub_pid" ] && kill "$stub_pid" 2>/dev/null; [ -n "$tmp" ] && rm -rf "$tmp"; }
trap cleanup EXIT

if [ "$with_stub" = 1 ]; then
  tmp="$(mktemp -d)"
  openssl req -x509 -newkey rsa:2048 -nodes -keyout "$tmp/key.pem" -out "$tmp/cert.pem" \
    -subj "/CN=localhost" -days 2 -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1 \
    || { echo "openssl could not make a certificate" >&2; exit 1; }
  python3 "$here/stub_provider.py" --cert "$tmp/cert.pem" --key "$tmp/key.pem" >"$tmp/stub.out" 2>&1 &
  stub_pid=$!
  for _ in 1 2 3 4 5 6 7 8 9 10; do grep -q '^tls ' "$tmp/stub.out" 2>/dev/null && break; sleep 0.3; done
  plain="$(awk '/^plain /{print $2}' "$tmp/stub.out")"; tls="$(awk '/^tls /{print $2}' "$tmp/stub.out")"
  [ -n "$plain" ] && [ -n "$tls" ] || { echo "stub did not start" >&2; cat "$tmp/stub.out" >&2; exit 1; }
  for r in $(python3 "$here/stub_provider.py" --list); do
    case "$r" in hang) continue ;; esac
    extra+=(--url "stub:$r=$plain/$r")
  done
  extra+=(--url "stub:hang=$plain/hang")
  extra+=(--url "tls-selfsigned=$tls/ok/success")
  extra+=(--url "tls-on-plain-port=https://${plain#http://}/ok/success")
  extra+=(--url "local:no-such-host=https://no-such-host.invalid/")
  extra+=(--url "local:refused-port=http://127.0.0.1:1/")
  extra+=(--url "local:blackhole=http://10.255.255.1/")
fi

mkdir -p "$here/results"
out="$here/results/${label}-$(date -u +%Y%m%dT%H%M%SZ).json"
"$bin" --label "$label" ${extra[@]+"${extra[@]}"} >"$out" || { echo "probe failed (exit $?); partial output in $out" >&2; exit 1; }
echo "saved $out"
