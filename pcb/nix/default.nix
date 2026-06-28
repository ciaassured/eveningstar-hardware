{
  perSystem =
    { pkgs, self', ... }:
    let
      kicadSymbolDir = "${pkgs.kicad.libraries.symbols}/share/kicad/symbols";
      withKicadSymbolDir =
        script:
        ''
          export KICAD_SYMBOL_DIR="${kicadSymbolDir}"
        ''
        + builtins.readFile script;
    in
    {
      packages = {
        pcb-review = pkgs.writeShellApplication {
          name = "eveningstar-pcb-review";
          runtimeInputs = [
            pkgs.coreutils
            pkgs.kicad
          ];
          text = withKicadSymbolDir ./scripts/pcb-review.sh;
        };

        drc = pkgs.writeShellApplication {
          name = "eveningstar-drc";
          runtimeInputs = [ pkgs.kicad ];
          text = withKicadSymbolDir ./scripts/drc.sh;
        };

        kicad-locality = pkgs.writeShellApplication {
          name = "eveningstar-kicad-locality";
          runtimeInputs = [
            pkgs.coreutils
            pkgs.ripgrep
          ];
          text = builtins.readFile ./scripts/kicad-locality.sh;
        };

        subtree-drift = pkgs.writeShellApplication {
          name = "eveningstar-subtree-drift";
          runtimeInputs = [
            pkgs.diffutils
            pkgs.git
            pkgs.gnutar
          ];
          text = builtins.readFile ./scripts/subtree-drift.sh;
        };

        default = self'.packages.drc;
      };

      apps = {
        pcb-review = {
          type = "app";
          program = "${self'.packages.pcb-review}/bin/eveningstar-pcb-review";
        };

        drc = {
          type = "app";
          program = "${self'.packages.drc}/bin/eveningstar-drc";
        };

        kicad-locality = {
          type = "app";
          program = "${self'.packages.kicad-locality}/bin/eveningstar-kicad-locality";
        };

        subtree-drift = {
          type = "app";
          program = "${self'.packages.subtree-drift}/bin/eveningstar-subtree-drift";
        };

        default = self'.apps.drc;
      };

      devShells.default = pkgs.mkShell {
        packages = [
          pkgs.kicad
        ];

        KICAD_SYMBOL_DIR = kicadSymbolDir;
      };
    };
}
