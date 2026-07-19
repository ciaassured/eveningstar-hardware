{
  perSystem =
    { pkgs, self', ... }:
    let
      kicadSymbolDir = "${pkgs.kicad.libraries.symbols}/share/kicad/symbols";
      # Keep the pinned fontconfig used by KiCad from parsing a potentially
      # incompatible host configuration under /etc/fonts.
      kicadFontconfigFile = pkgs.makeFontsConf {
        fontDirectories = [ ];
        impureFontDirectories = [ ];
        includes = [ ];
      };
      threeSource = pkgs.fetchurl {
        name = "three-0.184.0.tgz";
        url = "https://registry.npmjs.org/three/-/three-0.184.0.tgz";
        hash = "sha256-XIx1J4UE/zHO3Nc24EOwbBjyy/IgrX+F+/qhoI07NiY=";
      };
      reviewViewer = pkgs.runCommand "eveningstar-review-viewer.js" {
        nativeBuildInputs = [ pkgs.esbuild ];
      } ''
        mkdir -p source node_modules
        tar -xzf ${threeSource} -C source
        ln -s "$PWD/source/package" node_modules/three
        cp ${./scripts/review-viewer.js} review-viewer.js
        esbuild review-viewer.js \
          --bundle \
          --format=iife \
          --global-name=EveningStarViewer \
          --legal-comments=eof \
          --outfile="$out"
      '';
      withKicadEnvironment =
        script:
        ''
          export KICAD_SYMBOL_DIR="${kicadSymbolDir}"
          export FONTCONFIG_FILE="${kicadFontconfigFile}"
        ''
        + builtins.readFile script;
      publishTools = import ./publish.nix {
        inherit pkgs;
        source = ../..;
      };
      publishExpression = pkgs.writeText "eveningstar-publish-expression.nix" ''
        { source }:
        (import ${./publish.nix} {
          pkgs = import ${pkgs.path} { system = "${pkgs.stdenv.hostPlatform.system}"; };
          inherit source;
        }).artifacts
      '';
      reviewInputsExpression = pkgs.writeText "eveningstar-review-inputs-expression.nix" ''
        { destinationSource, sourceSource }:
        import ${./review-inputs.nix} {
          pkgs = import ${pkgs.path} { system = "${pkgs.stdenv.hostPlatform.system}"; };
          publishNix = ${./publish.nix};
          inherit destinationSource sourceSource;
        }
      '';
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

        review = pkgs.writeShellApplication {
          name = "eveningstar-review";
          runtimeInputs = [
            pkgs.coreutils
            pkgs.gh
            pkgs.git
            pkgs.gnutar
            pkgs.nix
            pkgs.nodejs-slim
          ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
            pkgs.xdg-utils
          ];
          text = ''
            export EVENINGSTAR_REVIEW_INPUTS_EXPRESSION="${reviewInputsExpression}"
            export EVENINGSTAR_REVIEW_VIEWER="${reviewViewer}"
            export EVENINGSTAR_REVIEW_UI="${./scripts/review-ui.js}"
            export EVENINGSTAR_REVIEW_SERVER="${./scripts/review-server.js}"
          '' + builtins.readFile ./scripts/review.sh;
        };

        publish = publishTools.artifacts;

        publish-command = pkgs.writeShellApplication {
          name = "eveningstar-publish";
          runtimeInputs = [
            pkgs.coreutils
            pkgs.nix
          ];
          text = ''
            publish_output="$(${pkgs.nix}/bin/nix build \
              --extra-experimental-features nix-command \
              --max-jobs auto \
              --file "${publishExpression}" \
              --arg source "${../..}" \
              --no-link \
              --print-out-paths)"
            destination="$PWD/reports/publish"
            rm -rf "$destination"
            mkdir -p "$(dirname "$destination")"
            ln -s "$publish_output" "$destination"
            echo "Publish artifacts:"
            echo "  $publish_output"
            echo "Linked from:"
            echo "  $destination"
          '';
        };

        schematic-documents = publishTools.schematicDocuments;

        pcb-documents = publishTools.pcbDocuments;

        render-plan = publishTools.renderPlan;

        render-sides = publishTools.renderSides;

        render-isometric = publishTools.renderIsometric;

        model-step = publishTools.stepModel;

        model-glb = publishTools.glbModel;

        drc = pkgs.writeShellApplication {
          name = "eveningstar-drc";
          runtimeInputs = [ pkgs.kicad ];
          text = withKicadEnvironment ./scripts/drc.sh;
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

        review = {
          type = "app";
          program = "${self'.packages.review}/bin/eveningstar-review";
        };

        publish = {
          type = "app";
          program = "${self'.packages.publish-command}/bin/eveningstar-publish";
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
          pkgs.gh
          pkgs.kicad
          pkgs.lefthook
          self'.packages.checks
          self'.packages.drc
          self'.packages.kicad-locality
          self'.packages.publish-command
          self'.packages.review
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
