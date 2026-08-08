# -*- coding: utf-8 -*-
"""One-shot enterprise auth setup for Supabase project uewqsczvyglahnqjhuvx.

This cannot invent OAuth/SMTP secrets. Export the vars below, then:

  python3 -m pipeline.enterprise_auth_setup

Required for dashboard-equivalent config (Management API):
  SUPABASE_ACCESS_TOKEN   — Account → Access Tokens (sbp_…)
  GOOGLE_CLIENT_ID        — Google Cloud OAuth Web client
  GOOGLE_CLIENT_SECRET

Optional:
  AZURE_CLIENT_ID / AZURE_SECRET   — Microsoft Entra
  RESEND_API_KEY                  — SMTP via Resend (smtp.resend.com)
  SMTP_ADMIN_EMAIL                — From address (default: noreply@isnad.news)
  SUPABASE_SERVICE_KEY            — service_role JWT (invite org membership)
  ENTERPRISE_INVITE_EMAIL         — user to add (default: soldiom@gmail.com)
  ENTERPRISE_ORG_NAME             — default: سَنَد
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

REF = os.environ.get("SUPABASE_PROJECT_REF", "uewqsczvyglahnqjhuvx")
SB_URL = os.environ.get("SUPABASE_URL", f"https://{REF}.supabase.co")
SITE = "https://www.isnad.news"
REDIRECTS = [
    "https://www.isnad.news/enterprise",
    "https://isnad.news/enterprise",
    "https://www.isnad.news/**",
    "https://isnad.news/**",
]


def _req(url: str, *, method: str = "GET", token: str, body: dict | None = None, extra: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "apikey": token,
    }
    if extra:
        headers.update(extra)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read().decode() or "{}"
            return r.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try:
            payload = json.loads(err)
        except Exception:
            payload = {"message": err[:500]}
        return e.code, payload


def configure_auth() -> int:
    pat = (os.environ.get("SUPABASE_ACCESS_TOKEN") or "").strip()
    if not pat:
        print("❌ missing SUPABASE_ACCESS_TOKEN (Supabase Account → Access Tokens)")
        return 2

    patch: dict = {
        "site_url": SITE,
        "uri_allow_list": ",".join(REDIRECTS),
    }

    gid = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    gsec = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    if gid and gsec:
        patch.update(
            {
                "external_google_enabled": True,
                "external_google_client_id": gid,
                "external_google_secret": gsec,
            }
        )
        print("→ enabling Google provider")
    else:
        print("⚠️  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set — skip Google")

    aid = (os.environ.get("AZURE_CLIENT_ID") or "").strip()
    asec = (os.environ.get("AZURE_SECRET") or os.environ.get("AZURE_CLIENT_SECRET") or "").strip()
    if aid and asec:
        patch.update(
            {
                "external_azure_enabled": True,
                "external_azure_client_id": aid,
                "external_azure_secret": asec,
            }
        )
        print("→ enabling Azure/Microsoft provider")
    else:
        print("⚠️  AZURE_CLIENT_ID / AZURE_SECRET not set — skip Microsoft")

    resend = (os.environ.get("RESEND_API_KEY") or "").strip()
    if resend:
        sender = (os.environ.get("SMTP_ADMIN_EMAIL") or "noreply@isnad.news").strip()
        patch.update(
            {
                "smtp_admin_email": sender,
                "smtp_host": "smtp.resend.com",
                "smtp_port": "465",
                "smtp_user": "resend",
                "smtp_pass": resend,
                "smtp_sender_name": "سَنَد",
            }
        )
        print(f"→ SMTP Resend as {sender}")
    else:
        print("⚠️  RESEND_API_KEY not set — built-in mail stays rate-limited")

    status, resp = _req(
        f"https://api.supabase.com/v1/projects/{REF}/config/auth",
        method="PATCH",
        token=pat,
        body=patch,
    )
    if status >= 400:
        print(f"❌ auth config PATCH {status}: {json.dumps(resp, ensure_ascii=False)[:400]}")
        return 1
    print(f"✅ auth config updated ({status})")
    # verify public settings
    st, settings = _req(
        f"{SB_URL}/auth/v1/settings",
        token=os.environ.get("SUPABASE_ANON_KEY")
        or "sb_publishable_vkQkzJ5s86bWd7lxPSeGTA_xNoahNaV",
    )
    ext = (settings or {}).get("external") or {}
    print(
        f"   public providers → google={ext.get('google')} azure={ext.get('azure')} email={ext.get('email')}"
    )
    return 0


def invite_member() -> int:
    sk = (os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()
    if not sk:
        print("⚠️  SUPABASE_SERVICE_KEY not set — skip sanad_orgs / sanad_members")
        return 0
    email = (os.environ.get("ENTERPRISE_INVITE_EMAIL") or "soldiom@gmail.com").strip().lower()
    org_name = (os.environ.get("ENTERPRISE_ORG_NAME") or "سَنَد").strip()

    # Ensure user exists (invite / magic)
    st, user = _req(
        f"{SB_URL}/auth/v1/admin/users",
        method="POST",
        token=sk,
        body={"email": email, "email_confirm": True},
        extra={"Authorization": f"Bearer {sk}"},
    )
    if st >= 400 and "already" not in json.dumps(user).lower():
        # fetch by email
        st2, listed = _req(
            f"{SB_URL}/auth/v1/admin/users?page=1&per_page=200",
            token=sk,
            extra={"Authorization": f"Bearer {sk}"},
        )
        users = (listed or {}).get("users") or []
        match = next((u for u in users if (u.get("email") or "").lower() == email), None)
        if not match:
            print(f"❌ could not create/find user {email}: {st} {user}")
            return 1
        uid = match["id"]
        print(f"→ found existing user {email}")
    else:
        uid = (user.get("id") or (user.get("user") or {}).get("id"))
        if not uid:
            st2, listed = _req(
                f"{SB_URL}/auth/v1/admin/users?page=1&per_page=200",
                token=sk,
                extra={"Authorization": f"Bearer {sk}"},
            )
            users = (listed or {}).get("users") or []
            match = next((u for u in users if (u.get("email") or "").lower() == email), None)
            uid = match and match["id"]
        print(f"→ user ready {email} · {uid}")

    if not uid:
        print("❌ no user id")
        return 1

    # Upsert org
    st, orgs = _req(
        f"{SB_URL}/rest/v1/sanad_orgs?select=id,name&limit=5",
        token=sk,
        extra={"Authorization": f"Bearer {sk}", "Prefer": "return=representation"},
    )
    if st >= 400:
        print(f"❌ read sanad_orgs {st}: {orgs}")
        return 1
    org = (orgs or [None])[0] if isinstance(orgs, list) and orgs else None
    if not org:
        st, created = _req(
            f"{SB_URL}/rest/v1/sanad_orgs",
            method="POST",
            token=sk,
            body={"name": org_name},
            extra={"Authorization": f"Bearer {sk}", "Prefer": "return=representation"},
        )
        if st >= 400:
            print(f"❌ create org {st}: {created}")
            return 1
        org = created[0] if isinstance(created, list) else created
        print(f"✅ created org {org.get('name')} · {org.get('id')}")
    else:
        print(f"→ org {org.get('name')} · {org.get('id')}")

    st, mem = _req(
        f"{SB_URL}/rest/v1/sanad_members",
        method="POST",
        token=sk,
        body={"org_id": org["id"], "user_id": uid, "role": "owner"},
        extra={
            "Authorization": f"Bearer {sk}",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    if st >= 400:
        print(f"❌ membership {st}: {mem}")
        return 1
    print(f"✅ membership owner → {email}")
    return 0


def main() -> int:
    print(f"🏛️ enterprise auth setup · project {REF}")
    rc = configure_auth()
    rc2 = invite_member()
    if rc or rc2:
        print("\nNeed secrets in the environment (do not commit them):")
        print("  SUPABASE_ACCESS_TOKEN  GOOGLE_CLIENT_ID  GOOGLE_CLIENT_SECRET")
        print("  RESEND_API_KEY         SUPABASE_SERVICE_KEY  ENTERPRISE_INVITE_EMAIL")
        return rc or rc2
    print("\nDone. Re-test https://www.isnad.news/enterprise")
    return 0


if __name__ == "__main__":
    sys.exit(main())
