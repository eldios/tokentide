# tokentide task runner. Run `just` for the list; the dev shell
# (flake.nix) provides just, gum, gh, esphome.

set shell := ["bash", "-euo", "pipefail", "-c"]

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
    esphome compile tokentide.yaml
    esphome compile tokentide-stick.yaml
    esphome compile tokentide-stick-joy.yaml

# Grab a live screenshot: just screenshot <device-ip> [out.png]
screenshot ip out="screenshot.png":
    ./tools/screenshot.sh {{ip}} {{out}}
