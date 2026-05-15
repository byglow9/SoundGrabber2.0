---
phase: 15
slug: cloudflare-tunnel
status: ready
created: 2026-05-15
sources:
  - https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
  - https://developers.cloudflare.com/tunnel/setup/
  - https://developers.cloudflare.com/tunnel/downloads/
  - https://developers.cloudflare.com/tunnel/advanced/local-management/create-local-tunnel/
  - https://developers.cloudflare.com/tunnel/advanced/local-management/as-a-service/
---

# Phase 15 — Cloudflare Tunnel Research

## Research Question

What does the planner need to know to expose the existing SoundGrabber notebook deployment through a temporary Cloudflare Tunnel, validate the public frontend flow, and avoid accidentally turning a temporary public test into an unmanaged production exposure?

## Summary

Cloudflare Tunnel is the right fit for Phase 15 because it creates outbound connections from the notebook to Cloudflare instead of requiring router port-forwarding or public residential IP exposure. The current phase context intentionally chooses a temporary `.trycloudflare.com` quick tunnel, not a named production tunnel. Cloudflare documents quick tunnels as a testing/development tool that generates a random `trycloudflare.com` subdomain and proxies it to a local server such as `http://localhost:8000`.

For SoundGrabber, this means the plan should not create DNS records, Cloudflare Access policies, a named tunnel, or a systemd service in this phase. It should instead install or verify `cloudflared`, verify the local Compose stack first, run `cloudflared tunnel --url http://localhost:8000` manually, copy the generated URL, and validate `/health` plus three full frontend downloads through that public URL.

## Key Findings

### Quick Tunnel behavior

- Cloudflare quick tunnels are designed for testing/development and do not require adding a site to Cloudflare DNS.
- `cloudflared tunnel --url http://localhost:8000` generates a random public `*.trycloudflare.com` URL and prints it in the terminal.
- The tunnel lives for the duration of the running `cloudflared` process. The plan should therefore keep the terminal/process visible and document how the operator can stop it later.
- Cloudflare notes quick tunnels may not work if a `config.yaml` file exists in `.cloudflared`; if this happens on the notebook, the executor should tell the operator to temporarily move/rename that file and retry.

### Installation on Ubuntu

- Cloudflare documents APT installation for Debian/Ubuntu using Cloudflare's package signing key and `https://pkg.cloudflare.com/cloudflared any main`.
- The plan should treat installation as a human checkpoint, per `15-CONTEXT.md` D-06, then verify with `cloudflared --version`.
- Because the notebook is Ubuntu Server from the v1.3 setup, APT installation is the default path. Direct `.deb` download is a fallback only if package repo installation fails.

### Service mode is future work

- Cloudflare recommends service mode for availability because it starts at boot and keeps the tunnel running while the origin is online.
- Linux service mode expects a named tunnel/config/credentials and is not the right first implementation for this temporary `trycloudflare` flow.
- Systemd service should be deferred with custom domain/named tunnel work. The Phase 15 plan should not add a `cloudflared` service file or modify `docker-compose.yml`.

### Origin and exposure model

- The existing application origin is `http://localhost:8000`. Cloudflare terminates HTTPS publicly and proxies to that local HTTP origin.
- The compose stack currently publishes `0.0.0.0:8000->8000`, which means the site is also reachable from the same Wi-Fi/LAN unless firewall or bind-address changes are made. The tunnel itself does not require LAN exposure; a future hardening phase can bind to `127.0.0.1:8000:8000` or enforce firewall rules.
- The context decision accepts that `/yonkou` is exposed while the quick tunnel is active. The plan must add a blocking gate that rejects example/default `ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET` before starting the tunnel.

## Recommended Plan Shape

1. **Preflight and host security gate**
   - Verify `docker compose ps` shows api/worker/redis up and Redis healthy.
   - Verify `curl http://localhost:8000/health` returns 200 locally.
   - Verify `.env` has non-example `ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET`.
   - Explain that `/yonkou` will be publicly reachable while the tunnel is active.

2. **Human checkpoint: install/verify cloudflared**
   - Provide official APT commands for Ubuntu.
   - Pause for the operator to run them on the notebook.
   - Verify `cloudflared --version`.

3. **Manual quick tunnel and public smoke test**
   - Run `cloudflared tunnel --url http://localhost:8000`.
   - Operator copies the generated `.trycloudflare.com` URL.
   - Verify `curl https://<trycloudflare-url>/health` returns 200 from a network outside Tailscale/LAN when possible.

4. **Frontend E2E validation**
   - Open `https://<trycloudflare-url>/` in a browser.
   - Submit 3 real beat URLs.
   - For each: job completes, WAV downloads, BPM and key are displayed.
   - API/curl can be used only as diagnostic support.

5. **Close-out warning**
   - Do not stop `cloudflared` automatically.
   - Explicitly tell the operator the public URL remains active and `/yonkou` remains exposed until they stop the process.
   - Record the stop action (`Ctrl+C` in the tunnel terminal, or kill the `cloudflared` process if detached).

## Validation Architecture

| Gate | Command / action | Expected result |
|------|------------------|-----------------|
| Compose running | `sudo docker compose ps` | api, worker, bgutil up; redis healthy |
| Local health | `curl -i http://localhost:8000/health` | HTTP 200 and `{"status":"ok"}` |
| Admin secrets | inspect notebook `.env` | `ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET` are not example/default values |
| cloudflared installed | `cloudflared --version` | exit 0 and version output |
| Quick tunnel active | `cloudflared tunnel --url http://localhost:8000` | terminal prints `https://*.trycloudflare.com` URL |
| Public health | `curl -i https://<trycloudflare-url>/health` | HTTP 200 and `{"status":"ok"}` |
| Public frontend E2E | browser through public URL | 3 downloads complete with valid WAV, BPM, key |
| Exposure warning | final checklist | operator acknowledges tunnel stays active until stopped |

## Pitfalls and Mitigations

| Pitfall | Impact | Mitigation |
|---------|--------|------------|
| Treating quick tunnel as production | Random URL/process lifecycle means unstable public access | Mark domain/systemd as deferred; close Phase 15 only as technical validation |
| Starting tunnel before app is healthy | Public URL points to broken app | Gate on local Compose and `/health` first |
| Default admin credentials exposed | `/yonkou` reachable from public URL | Blocking gate on `ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET` |
| Forgetting tunnel remains active | Public access persists longer than intended | Final warning and stop instructions |
| Existing `.cloudflared/config.yaml` blocks quick tunnel | Quick tunnel command may fail | Document temporary rename/move of config file before retry |
| LAN exposure confused with tunnel exposure | Same-Wi-Fi users can access direct `:8000` while compose binds `0.0.0.0` | Note as future hardening; not required for quick tunnel validation |

## Security Notes

- Do not commit tunnel URLs, tokens, Cloudflare credentials, admin passwords, cookies, or `.env` contents.
- Do not add `privileged: true`, `network_mode: host`, or new exposed service ports.
- Do not add Cloudflare Access or route-level blocking in this phase unless the user explicitly starts a future hardening phase; `/yonkou` exposure is accepted temporarily by `15-CONTEXT.md`.

## Planning Constraints

- Every plan must cover TUNNEL-01 and/or TUNNEL-02 explicitly in frontmatter.
- Plans should use checkpoint tasks for notebook-side installation and browser-based E2E validation.
- The phase should likely be one or two plans, not a large multi-wave implementation, because most work is operational validation and documentation rather than code changes.
- If a plan modifies source, likely files are planning docs only; code changes are not expected unless the planner intentionally adds a helper checklist/doc.
