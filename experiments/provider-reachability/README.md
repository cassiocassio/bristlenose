# Provider reachability probe

Records what a macOS app can know about its network when an LLM call is refused, so the
diagnosis in `docs/design-provider-problem-diagnosis.md` rests on measurement. Keyless: no
API key and no user data are sent, only to Apple's captive-portal host, the providers'
public endpoints, loopback, and whatever you pass with `--url` / `--azure-host`. Changes no
system setting.

```bash
cd experiments/provider-reachability
./run.sh baseline --with-stub                 # unsandboxed; writes results/<label>-<time>.json
./run.sh baseline --with-stub --sandboxed     # App-Sandboxed build (what the app is)
./run.sh baseline --with-stub --sandboxed-ats # plus an ATS exception for captive.apple.com
./summarise.py results/*.json --only control-https,anthropic,openai,gemini
```

`--with-stub` also starts `stub_provider.py` on loopback (provider-shaped 400/401/402/429/
5xx/529 replies, proxy block pages, portal replies, hang/reset/garbage) and probes the local
failure cases (no such host, refused port, black-holed address, self-signed certificate,
https to a plain-http port). `./stub_provider.py --list` names the routes. `results/` and
`.build/` are gitignored; the files hold your gateway address and interface names.

Each file records: macOS version, whether sandboxed, NWPathMonitor state (status, reason,
interfaces, gateways, `uses_other` for VPN tunnels), a cellular-only path as the shape of an
unsatisfied path, system proxy settings, getaddrinfo answers with an address class
(public / private / loopback / unspecified / link-local / cgnat), a TCP probe of the gateway
on 53/80/443 (`waiting` + ECONNREFUSED means the router answered, so it is alive), and for
every request the URLError code and name, `_kCFStreamError*` codes, HTTP status, all
headers, a 300-byte body prefix, and elapsed ms.

## States to run (each needs your hands)

Run `./run.sh <label> --sandboxed` (add `--with-stub` once per state; the stub cases do not
depend on the network) in each, then `./summarise.py results/*.json`. Revert after each.

1. **Wi-Fi off** (menu bar, or `networksetup -setairportpower en0 off`). Label `wifi-off`.
   Expect path `unsatisfied`, no gateways, every request -1009. Also run with Wi-Fi *on but
   joined to nothing* (join a dead SSID) as `wifi-no-network`.
2. **WAN unplugged**: router up, its internet cable out, or a phone hotspot with mobile data
   off. Label `wan-down`. Expect path `satisfied`, gateway port 53 or a refusal answering,
   control probe failing with -1009/-1003/-1001. Compare timings: which fails fast?
3. **Captive portal**: join a hotel/café Wi-Fi before signing in (or a hotspot you control
   that redirects). Label `portal`. Watch `control-http` (status 302/200 with a body that is
   not "Success") against `control-https` (TLS error). Do not sign in until after the run.
4. **VPN up, then dropped**: `vpn-up`, then drop it with the tunnel's kill-switch off
   (`vpn-dropped`) and, if your VPN has one, with it on (`vpn-killswitch`). Look at
   `path.uses_other` and the interface list.
5. **DNS sinkhole for the provider host**: add `0.0.0.0 api.anthropic.com` (second run:
   `127.0.0.1 api.anthropic.com`) to `/etc/hosts` (`sudo`), label `dns-sinkhole`, then
   **remove the lines and `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`**.
   Expect the DNS block to show class `unspecified`/`loopback`, and the request to fail
   -1004 or -1001 instead of -1003.
6. **TLS interception**: `brew install mitmproxy`, `mitmdump --listen-port 8080`, point the
   system HTTPS proxy at 127.0.0.1:8080 in Network settings *without* installing its CA, label
   `tls-intercept`; **turn the proxy off afterwards**. Expect -1202 for the providers and the
   control host. Also try mitmproxy's `--mode upstream`/a 403 `block` script to get a proxy
   block page (row 7): expect an HTTP reply with no `request-id`.
7. **Wrong system clock**: System Settings > General > Date & Time, turn off "Set
   automatically", set the date a year ahead (`wrong-clock-future`) and a year back
   (`wrong-clock-past`); **turn "Set automatically" back on**. Expect -1201
   (serverCertificateHasBadDate) or -1204 on every HTTPS request, control host included. This
   is the one that separates row 4 from row 6 (-1202), if it holds.
8. **macOS 15 vs 26 `.status` toolbar zone** on a VM guest: boot a macOS 15 guest and a 26
   guest, run Diagnostics > Provider problem pill (the DEBUG prototype), and note where the
   `.status` item lands (centre on 26 per the mockup) and whether the title-bar controls
   collide with it at the window's minimum width. Also run `./run.sh guest-15 --sandboxed
   --with-stub` there: the ATS result (plain HTTP to apple.com hosts needing no exception) was
   measured on 27.0 only.

Add `--azure-host <your-resource>.openai.azure.com` in a state to measure your own Azure
host's keyless reply.
