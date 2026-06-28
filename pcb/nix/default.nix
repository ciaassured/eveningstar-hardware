{
  perSystem =
    { pkgs, self', ... }:
    let
      kicadSymbolDir = "${pkgs.kicad.libraries.symbols}/share/kicad/symbols";
    in
    {
      packages = {
        drc = pkgs.writeShellApplication {
          name = "eveningstar-drc";
          runtimeInputs = [ pkgs.kicad ];
          text = ''
            set +e

            export KICAD_SYMBOL_DIR="${kicadSymbolDir}"
            mkdir -p reports

            echo "::group::KiCad ERC"
            kicad-cli sch erc \
              --severity-error \
              --severity-warning \
              --exit-code-violations \
              --format report \
              --output reports/erc.rpt \
              pcb/EveningStar.kicad_sch
            erc_status=$?
            cat reports/erc.rpt
            echo "::endgroup::"

            echo "::group::KiCad DRC"
            kicad-cli pcb drc \
              --severity-error \
              --severity-warning \
              --schematic-parity \
              --exit-code-violations \
              --format report \
              --output reports/drc.rpt \
              pcb/EveningStar.kicad_pcb
            drc_status=$?
            cat reports/drc.rpt
            echo "::endgroup::"

            if [ "$erc_status" -ne 0 ] || [ "$drc_status" -ne 0 ]; then
              exit 1
            fi
          '';
        };

        default = self'.packages.drc;
      };

      apps = {
        drc = {
          type = "app";
          program = "${self'.packages.drc}/bin/eveningstar-drc";
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
