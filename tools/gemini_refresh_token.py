#!/usr/bin/env python3
"""One-time Google login that mints the refresh token TokenTide's Gemini
provider keeps on the device (packages/provider-gemini.yaml).

Runs the OAuth loopback flow with the Antigravity OAuth client, the client
agy itself signs in with, and prints the secrets.yaml lines. Nothing is
written to disk.

    python3 tools/gemini_refresh_token.py

The client secret is read from GEMINI_CLIENT_SECRET or prompted for. It is
the ClientSecret constant of the Antigravity client in CLIProxyAPI
(https://pkg.go.dev/github.com/router-for-me/CLIProxyAPI/v7/internal/auth/antigravity),
also embedded in the agy binary.
"""

import base64
import getpass
import hashlib
import http.server
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

# Antigravity OAuth client, scopes and loopback port: CLIProxyAPI
# internal/auth/antigravity (ClientID, Scopes, CallbackPort). The device
# defaults to the same client id (components/tokentide_poller/__init__.py).
CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]
PORT = 51121
REDIRECT_URI = f"http://localhost:{PORT}/oauth-callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def wait_for_code(state):
    """Serve one request on the loopback redirect and return its code."""
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path != "/oauth-callback":
                self.send_error(404)
                return
            query = urllib.parse.parse_qs(url.query)
            result["state"] = query.get("state", [""])[0]
            result["code"] = query.get("code", [""])[0]
            result["error"] = query.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"TokenTide: login received, return to the terminal.\n")

        def log_message(self, *args):
            pass

    with http.server.HTTPServer(("127.0.0.1", PORT), Handler) as server:
        while "code" not in result:
            server.handle_request()
    if result["error"]:
        sys.exit(f"Login failed: {result['error']}")
    if result["state"] != state:
        sys.exit("Login failed: state mismatch")
    return result["code"]


def open_browser(url):
    """Open url with stdout pointed at stderr: the opener (xdg-open, gio)
    inherits our descriptors and must not mix its output with the secrets."""
    saved = os.dup(1)
    os.dup2(2, 1)
    try:
        webbrowser.open(url)
    finally:
        os.dup2(saved, 1)
        os.close(saved)


def main():
    client_secret = os.environ.get("GEMINI_CLIENT_SECRET") or getpass.getpass("Antigravity client secret: ")
    if not client_secret:
        sys.exit("GEMINI_CLIENT_SECRET is required")

    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    print("Open this URL and sign in with the Google account to monitor:\n\n" + url + "\n", file=sys.stderr)
    open_browser(url)
    code = wait_for_code(state)

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body)) as resp:
            tokens = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"Token exchange failed: HTTP {e.code} {e.read().decode(errors='replace')}")
    refresh = tokens.get("refresh_token")
    if not refresh:
        sys.exit("The token response carried no refresh_token")

    print("# Add to secrets.yaml (keep it out of git):", file=sys.stderr)
    print(f'gemini_refresh_token: "{refresh}"')
    print(f'gemini_client_secret: "{client_secret}"')


if __name__ == "__main__":
    main()
