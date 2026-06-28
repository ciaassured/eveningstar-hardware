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

        subtree-drift = pkgs.writeShellApplication {
          name = "eveningstar-subtree-drift";
          runtimeInputs = [
            pkgs.diffutils
            pkgs.git
            pkgs.gnutar
          ];
          text = ''
            set -euo pipefail

            subtree_dir="pcb/lib/JLCPCB-Kicad-Library"

            if [ ! -d "$subtree_dir" ]; then
              echo "::error::Expected subtree directory '$subtree_dir' does not exist"
              exit 1
            fi

            if ! git cat-file -e "HEAD:$subtree_dir"; then
              echo "::error::Expected subtree directory '$subtree_dir' is not present in HEAD"
              exit 1
            fi

            worktree_drift="$(git status --porcelain --untracked-files=all -- "$subtree_dir")"
            if [ -n "$worktree_drift" ]; then
              echo "::error::Uncommitted or untracked non-ignored files found in '$subtree_dir'"
              echo
              echo "Do not edit files in '$subtree_dir' directly. Copy symbols/footprints/models"
              echo "into a project-owned library and reference that copy instead."
              echo
              echo "$worktree_drift"
              exit 1
            fi

            squash_commit="$(
              git log \
                --all \
                --grep="^git-subtree-dir: $subtree_dir$" \
                --format=%H \
                -n 1
            )"

            if [ -z "$squash_commit" ]; then
              echo "::error::Could not find git-subtree metadata for '$subtree_dir'"
              echo "Run this check from a full clone. In CI, actions/checkout must use fetch-depth: 0."
              exit 1
            fi

            split_commit="$(
              git show -s --format=%B "$squash_commit" \
                | sed -n 's/^git-subtree-split: //p' \
                | tail -n 1
            )"

            expected_dir="$(mktemp -d)"
            actual_dir="$(mktemp -d)"
            trap 'rm -rf "$expected_dir" "$actual_dir"' EXIT

            git archive "$squash_commit" | tar -x -C "$expected_dir"
            git archive "HEAD:$subtree_dir" | tar -x -C "$actual_dir"

            if ! diff_output="$(git diff --no-index --name-status -- "$expected_dir" "$actual_dir")"; then
              echo "::error::Vendored subtree drift detected in '$subtree_dir'"
              echo
              echo "The vendored JLCPCB subtree differs from its recorded subtree squash commit:"
              echo "  subtree commit: $squash_commit"
              if [ -n "$split_commit" ]; then
                echo "  upstream split: $split_commit"
              fi
              echo
              echo "Do not edit files in '$subtree_dir' directly. Copy symbols/footprints/models"
              echo "into a project-owned library and reference that copy instead."
              echo
              echo "Changed files:"
              echo "$diff_output"
              exit 1
            fi

            echo "Subtree '$subtree_dir' matches recorded subtree commit $squash_commit."
            if [ -n "$split_commit" ]; then
              echo "Upstream split: $split_commit"
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
