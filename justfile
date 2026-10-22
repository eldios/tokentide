# tokentide task runner. Run `just` for the list; the dev shell
# (flake.nix) provides just, gum, gh, esphome.

set shell := ["bash", "-euo", "pipefail", "-c"]

# Prints the entry file chosen for a board (see _entry).
entry := quote(just_executable()) + " --justfile " + quote(justfile()) + " _entry"

default:
    @just --list

# Guided release (gum): checks, signed tag, stable branch, push, GH release
release:
    #!/usr/bin/env bash
    set -euo pipefail

    say() { gum style --foreground 212 "$1"; }
    die() { gum style --foreground 196 "ERROR: $1"; exit 1; }

    command -v gum >/dev/null || { echo "gum not found - run inside the dev shell (nix develop)"; exit 1; }

    [ -z "$(git status --porcelain)" ] || die "working tree is not clean"
    say "Fetching origin..."
    git fetch origin main --tags --quiet

    last="$(git tag --list 'v*' --sort=-version:refname | head -1)"
    [ -n "$last" ] || last="v0.0.0"
    next="$(echo "${last#v}" | awk -F. '{ printf "%d.%d.%d", $1, $2, $3 + 1 }')"

    say "Last release: $last"
    ver="$(gum input --value "$next" --prompt "New version (no leading v): ")"
    [[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "'$ver' is not X.Y.Z"
    tag="v$ver"

    git rev-parse -q --verify "refs/tags/$tag" >/dev/null && die "tag $tag already exists"

    # The firmware must report the version being released, or every
    # device flags a phantom update forever.
    fw="$(git show origin/main:packages/common.yaml | sed -n 's/^ *tokentide_version: "\(.*\)"/\1/p')"
    [ "$fw" = "$ver" ] || die "tokentide_version on origin/main is '$fw', not '$ver' - bump packages/common.yaml and land it first"

    say "Tag message (edit, then Ctrl-D):"
    msg="$(gum write --value "tokentide $tag" --width 72 --height 6)"
    [ -n "$msg" ] || die "empty tag message"

    gum style --border rounded --padding "0 2" "tag: $tag (signed, on origin/main)" "stable -> $tag" "push: origin $tag stable" "gh release create $tag --generate-notes"
    gum confirm "Release $tag?" || die "aborted"

    git tag -s "$tag" origin/main -m "$msg"
    git tag -v "$tag" >/dev/null 2>&1 || die "tag signature verification failed"
    git branch -f stable "$tag"
    git push origin "$tag" stable
    gh release create "$tag" --generate-notes
    say "Released $tag - stable moved, GitHub release live."

# Host unit tests for the pure C++ helpers.
test:
    mkdir -p .esphome/tests
    c++ -std=c++20 -Wall -Wextra -Werror -o .esphome/tests/usage_window_test tests/usage_window_test.cpp
    .esphome/tests/usage_window_test

# Local gate: host tests, then every board build.
ci: test build-all

# Build every board variant (local dev entry points).
build-all:
    esphome compile devices/tokentide.yaml
    esphome compile devices/tokentide-stick.yaml
    esphome compile devices/tokentide-stick-joy.yaml

# Compile and upload: target /dev/... flashes over USB, an IP or hostname over OTA, none asks
flash board target="":
    @entry="$({{entry}} {{quote(board)}})" && esphome run "$entry" {{ if target == "" { "" } else { "--device " + quote(target) } }}

# Live logs, same target rule as flash
logs board target="":
    @entry="$({{entry}} {{quote(board)}})" && esphome logs "$entry" {{ if target == "" { "" } else { "--device " + quote(target) } }}

# Compile one board: cores3, stick or stick-joy
compile board:
    @entry="$({{entry}} {{quote(board)}})" && esphome compile "$entry"

# USB serial ports to pass as the flash/logs target
ports:
    @ls -1 /dev/serial/by-id/* 2>/dev/null || echo "no USB serial device found in /dev/serial/by-id"

# Google login for the Gemini provider; prints the two gemini_* secrets.yaml lines
gemini-token:
    python3 tools/gemini_refresh_token.py

# Remove the ESPHome build cache and the host test binaries
clean:
    rm -rf devices/.esphome .esphome

# Grab a live screenshot: just screenshot <device-ip> [out.png]
screenshot ip out="screenshot.png":
    ./tools/screenshot.sh {{ip}} {{out}}

# Entry file for a board: the gitignored *-local.yaml when present, else the tracked one
_entry board:
    #!/usr/bin/env bash
    set -euo pipefail
    board={{quote(board)}}
    case "$board" in
        cores3) base=tokentide ;;
        stick) base=tokentide-stick ;;
        stick-joy) base=tokentide-stick-joy ;;
        *) echo "unknown board '$board' - use cores3, stick or stick-joy" >&2; exit 1 ;;
    esac
    for f in "devices/$base-local.yaml" "devices/$base.yaml"; do
        if [ -f "$f" ]; then
            echo "board $board: $f" >&2
            echo "$f"
            exit 0
        fi
    done
    echo "board $board: neither devices/$base-local.yaml nor devices/$base.yaml exists" >&2
    exit 1
