{
  description = "tokentide dev environment: ESPHome build/flash tooling";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forEachSystem = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forEachSystem (pkgs: {
        default = pkgs.mkShell {
          packages = [
            pkgs.esphome # build, flash (USB + OTA), logs
            pkgs.esptool # bare-metal chip probing when needed
            pkgs.just # task runner (see justfile)
            pkgs.gum # interactive prompts for `just release`
            pkgs.gh # GitHub release creation
            pkgs.imagemagick # tools/screenshot.sh BMP -> PNG
            pkgs.python3 # just gemini-token
          ];
        };
      });
    };
}
