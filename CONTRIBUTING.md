# Contributing to tokentide

Thanks for helping! A few ground rules keep this repo healthy.

## Dev setup

- Nix: `nix develop` gives you `esphome`, `esptool` and `just`.
- Otherwise: any ESPHome >= 2026.4.0 install works (`pipx install esphome`).
- `cp secrets.example.yaml secrets.yaml`, fill in WiFi and your
  `claude setup-token` output, then `just flash cores3`.

`just` lists every recipe. The device ones take a board (`cores3`,
`stick` or `stick-joy`) and use its `*-local.yaml` entry when it exists,
otherwise the tracked one:

- `just flash <board> [target]` compiles and uploads; `just logs <board>
  [target]` follows the logs. A `/dev/...` target goes over USB, an IP or
  hostname over the network; with no target ESPHome asks.
- `just ports` lists the USB serial ports to use as a target.
- `just compile <board>` builds one board, `just build-all` all of them.
- `just gemini-token` runs the Google login and prints the two
  `gemini_*` lines for `secrets.yaml`.
- `just clean` removes the `.esphome` build cache.

## Before opening a PR

1. `esphome config tokentide.yaml` must pass (schema validation).
2. `just ci` must pass (host tests and every board build).
3. If you touched UI or hardware bits, test on a real CoreS3 and say so in
   the PR ("tested on hardware: yes/no" plus what you exercised).

## Hardware facts need sources

Pin numbers, register values, and component options must come from a
canonical source - M5Stack's official ESPHome configs
(github.com/m5stack/esphome-yaml), the CoreS3 schematic, or the ESPHome
docs for the exact release. Link the source in the PR description.
"It worked for me" without a source is how ports rot.

## Style

- YAML: two-space indent, comments explain WHY, keep packages focused
  (hardware / poller / ui stay separate).
- Lambdas: keep them short; if C++ grows past a screenful it probably
  belongs in an external component.
- User-facing strings and docs are in English.

## Adding a board

The layout is built for it - one board = one entry file, reusing the
shared engine:

1. `packages/hardware-<name>.yaml` - display, touch (if any), power,
   buses. Source every pin from canonical references.
2. Pick a UI package matching the display class, or add one
   (`packages/ui-<W>x<H>-<class>.yaml`). The poller
   (`packages/usage-poller.yaml`) is board-agnostic - do not fork it.
3. `boards/<name>.yaml` - SoC/framework config + `packages:` include of
   common, hardware, poller, and the UI. Same substitutions contract as
   the CoreS3 entry (`claude_token`, `poll_interval`, `name`).
4. Add the board to the README table with its status ("tested on
   hardware" or "untested") and the import snippet.

UI packages must always show at minimum: the 5h utilization, a 7d
indicator, and the polling cost (req/day). Screens too small for the rest
should drop features, not shrink them into unreadability - that is the
whole point of this project.

## Releasing

1. Bump `tokentide_version` in `packages/common.yaml` to `X.Y.Z` in the
   change that lands the release on `main`. The component source and the
   sprite bases load from the tag `vX.Y.Z`, so remote builds of `main`
   fail until that tag exists. `just release` refuses to tag while
   `origin/main` reports another version.
2. Land everything on `main`, verify on hardware.
3. Signed tag: `git tag -s vX.Y.Z main -m "..."`.
4. Move the floating release branch: `git branch -f stable vX.Y.Z`.
5. Push tag and branch: `git push origin vX.Y.Z stable`.
6. Create the GitHub release: `gh release create vX.Y.Z --generate-notes`.

Users on `ref: stable` pick the release up at their next Install; pinned
users bump their `ref:` when they choose to.
