# thelunale.com — GitHub Pages + Cloudflare setup

## 1. Push to the repo

Add these two new files to `pasha4j/lunale` on the `main` branch (root of the repo):

- `index.html` — the renamed copy of `lunale.html`
- `CNAME` — a one-line file containing exactly `thelunale.com` (no trailing newline)

You can keep `lunale.html` for now or delete it; GitHub Pages will serve `index.html` at the root either way.

## 2. Register thelunale.com (Cloudflare Registrar)

Cheapest at-cost pricing and zero DNS migration needed.

1. Sign in at https://dash.cloudflare.com → **Domain Registration → Register**.
2. Search `thelunale.com`, add to cart, complete checkout.
3. After registration the domain auto-appears in your Cloudflare account with DNS managed by Cloudflare nameservers.

If you'd rather register elsewhere (Namecheap, Porkbun, Google Domains successor, etc.): register the domain, then in Cloudflare click **Add a site**, follow the wizard, and update the nameservers at the registrar to the two Cloudflare nameservers Cloudflare assigns you. Wait for propagation (usually under an hour) before continuing.

## 3. Configure Cloudflare DNS

In the Cloudflare dashboard, open `thelunale.com` → **DNS → Records**. Delete any default A/AAAA/CNAME records on `@` or `www` first, then add:

Apex (thelunale.com → GitHub Pages) — four A records on `@`:

```
A   @   185.199.108.153   Proxy: DNS only (gray cloud)
A   @   185.199.109.153   Proxy: DNS only
A   @   185.199.110.153   Proxy: DNS only
A   @   185.199.111.153   Proxy: DNS only
```

Optional IPv6 (recommended) — four AAAA records on `@`:

```
AAAA  @   2606:50c0:8000::153   Proxy: DNS only
AAAA  @   2606:50c0:8001::153   Proxy: DNS only
AAAA  @   2606:50c0:8002::153   Proxy: DNS only
AAAA  @   2606:50c0:8003::153   Proxy: DNS only
```

`www` subdomain — one CNAME so `www.thelunale.com` also works:

```
CNAME  www   pasha4j.github.io   Proxy: DNS only
```

**Why "DNS only" / gray cloud?** GitHub Pages issues its own Let's Encrypt certificate and needs to see the requests directly to renew it. The orange "proxied" cloud puts Cloudflare in front, which conflicts with GitHub's cert provisioning unless you set Cloudflare's SSL/TLS mode to "Full" (not "Flexible", which causes redirect loops). Start gray; you can switch to orange later if you want Cloudflare's caching/analytics, but only after switching SSL/TLS mode to **Full** in Cloudflare → SSL/TLS → Overview.

## 4. Enable GitHub Pages

1. Open https://github.com/pasha4j/lunale/settings/pages
2. Under **Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/ (root)`. Save.
4. Under **Custom domain**, GitHub should auto-detect `thelunale.com` from the CNAME file. If it doesn't, type it and click Save.
5. GitHub will run a DNS check. Once the apex A records resolve, it shows a green check.
6. After the DNS check passes, the **Enforce HTTPS** checkbox unlocks (can take 5–30 minutes for the cert; sometimes up to 24h on a brand-new domain). Tick it.

## 5. Verify

```
dig thelunale.com +short          # should return the four 185.199.x.153 IPs
dig www.thelunale.com +short      # should return pasha4j.github.io. then the same IPs
curl -I https://thelunale.com     # HTTP/2 200, server: GitHub.com
```

Then open https://thelunale.com in a browser — you should see Lunale.

## Troubleshooting

- **DNS check fails on GitHub:** confirm the A records are gray-cloud (DNS only). Orange-cloud breaks the check.
- **"Domain does not resolve" warning:** wait 10–15 min, then click "Check again" on the Pages settings page.
- **HTTPS toggle stays disabled:** GitHub is still issuing the cert. Be patient; check back later.
- **Loops between HTTP and HTTPS:** if you ever turn on Cloudflare proxy, set SSL/TLS mode to **Full** (or **Full (strict)**), never **Flexible**.
