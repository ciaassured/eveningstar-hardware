{
  description = "EveningStar project tooling";

  inputs = {
    fabrication-toolkit = {
      url = "github:bennymeg/Fabrication-Toolkit/642b069c28e1f12d357c625a8d16ab3d81230712";
      flake = false;
    };
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-darwin"
        "x86_64-linux"
      ];

      imports = [
        ./pcb/nix
      ];
    };
}
