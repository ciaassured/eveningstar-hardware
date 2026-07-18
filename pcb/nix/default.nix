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
        checks = pkgs.writeShellApplication {
          name = "eveningstar-checks";
          runtimeInputs = [
            self'.packages.drc
            self'.packages.kicad-locality
            self'.packages.subtree-drift
          ];
          text = builtins.readFile ./scripts/checks.sh;
        };

        pcb-review = pkgs.writeShellApplication {
          name = "eveningstar-pcb-review";
          runtimeInputs = [
            pkgs.coreutils
            pkgs.kicad
          ];
          text = withKicadSymbolDir ./scripts/pcb-review.sh;
        };

        pcb-renders = pkgs.writeShellApplication {
          name = "eveningstar-pcb-renders";
          runtimeInputs = [
            pkgs.coreutils
            pkgs.kicad
          ];
          text = withKicadSymbolDir ./scripts/pcb-renders.sh;
        };

        pcb-models = pkgs.writeShellApplication {
          name = "eveningstar-pcb-models";
          runtimeInputs = [
            pkgs.coreutils
            pkgs.kicad
          ];
          text = withKicadSymbolDir ./scripts/pcb-models.sh;
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

        default = self'.packages.checks;
      };

      apps = {
        checks = {
          type = "app";
          program = "${self'.packages.checks}/bin/eveningstar-checks";
        };

        pcb-review = {
          type = "app";
          program = "${self'.packages.pcb-review}/bin/eveningstar-pcb-review";
        };

        pcb-renders = {
          type = "app";
          program = "${self'.packages.pcb-renders}/bin/eveningstar-pcb-renders";
        };

        pcb-models = {
          type = "app";
          program = "${self'.packages.pcb-models}/bin/eveningstar-pcb-models";
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

        default = self'.apps.checks;
      };

      devShells.default = pkgs.mkShell {
        packages = [
          pkgs.kicad
          pkgs.lefthook
          self'.packages.checks
          self'.packages.drc
          self'.packages.kicad-locality
          self'.packages.pcb-models
          self'.packages.pcb-renders
          self'.packages.pcb-review
          self'.packages.subtree-drift
        ];

        KICAD_SYMBOL_DIR = kicadSymbolDir;

        shellHook = ''
          if ${pkgs.git}/bin/git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
            if ! ${pkgs.lefthook}/bin/lefthook install >/dev/null; then
              echo "warning: could not install the EveningStar Git hooks" >&2
              echo "run 'lefthook install' for details" >&2
            fi
          fi
        '';
      };
    };
}
