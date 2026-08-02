{
  pkgs,
  source,
  fabricationToolkit,
  productionScript ? ./scripts/production.py,
  turntableScript ? ./scripts/turntable.py,
}:

let
  sourceRoot = toString source;
  hardwareSource = builtins.path {
    name = "eveningstar-hardware-source";
    path = source;
    filter =
      path: _type:
      let
        relative = pkgs.lib.removePrefix "${sourceRoot}/" (toString path);
        isPcb = relative == "pcb" || pkgs.lib.hasPrefix "pcb/" relative;
        isTooling = relative == "pcb/nix" || pkgs.lib.hasPrefix "pcb/nix/" relative;
        isGenerated =
          relative == "pcb/EveningStar-backups"
          || pkgs.lib.hasPrefix "pcb/EveningStar-backups/" relative
          || relative == "pcb/pcb"
          || pkgs.lib.hasPrefix "pcb/pcb/" relative
          || relative == "pcb/reports"
          || pkgs.lib.hasPrefix "pcb/reports/" relative
          # Keep local plugin output and historical revisions that committed it
          # from becoming inputs to a fresh production build.
          || relative == "pcb/production"
          || pkgs.lib.hasPrefix "pcb/production/" relative
          || pkgs.lib.hasSuffix ".bak" relative
          || pkgs.lib.hasSuffix ".kicad_prl" relative
          || pkgs.lib.hasSuffix ".lck" relative;
      in
      relative == "" || (isPcb && !isTooling && !isGenerated && relative != "pcb/README.md");
  };
  kicadSymbolDir = "${pkgs.kicad.libraries.symbols}/share/kicad/symbols";
  kicadPythonPath =
    "${pkgs.kicad.base}/lib/python${pkgs.python3.pythonVersion}/site-packages";
  mkKicadDerivation =
    {
      name,
      nativeBuildInputs ? [ ],
      build,
    }:
    pkgs.runCommand name {
      src = hardwareSource;
      nativeBuildInputs = [ pkgs.kicad ] ++ nativeBuildInputs;
    } ''
      build_home="$TMPDIR/home"
      mkdir -p "$build_home" "$TMPDIR/config" "$TMPDIR/cache"
      export HOME="$build_home"
      export XDG_CONFIG_HOME="$TMPDIR/config"
      export XDG_CACHE_HOME="$TMPDIR/cache"
      export KICAD_SYMBOL_DIR="${kicadSymbolDir}"
      ${build}
    '';

  modelEnvironment = ''
    third_party_dir="$TMPDIR/third-party"
    mkdir -p "$third_party_dir/3dmodels"
    ln -s "$src/pcb/lib/JLCPCB-Kicad-Library/3dmodels" \
      "$third_party_dir/3dmodels/com_github_CDFER_JLCPCB-Kicad-Library"
    export KICAD10_3RD_PARTY="$third_party_dir"
    export KICAD8_3RD_PARTY="$third_party_dir"
    export KICAD_3RD_PARTY="$third_party_dir"
  '';

  schematicDocuments = mkKicadDerivation {
    name = "eveningstar-schematic-documents";
    build = ''
      mkdir -p "$out/svg"
      kicad-cli sch export pdf \
        --exclude-pdf-property-popups \
        --output "$out/EveningStar-schematic.pdf" \
        "$src/pcb/EveningStar.kicad_sch"
      kicad-cli sch export svg \
        --output "$out/svg" \
        "$src/pcb/EveningStar.kicad_sch"
    '';
  };

  pcbDocuments = mkKicadDerivation {
    name = "eveningstar-pcb-documents";
    build = ''
      mkdir -p "$out/pdf" "$out/svg/layers"
      kicad-cli pcb export pdf \
        --mode-single \
        --layers F.Cu,F.Mask,F.Silkscreen,F.Fab,Edge.Cuts \
        --output "$out/pdf/EveningStar-front.pdf" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb export pdf \
        --mode-single \
        --mirror \
        --layers B.Cu,B.Mask,B.Silkscreen,B.Fab,Edge.Cuts \
        --output "$out/pdf/EveningStar-back.pdf" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb export pdf \
        --mode-multipage \
        --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Fab,B.Fab,Edge.Cuts \
        --output "$out/pdf/EveningStar-layers.pdf" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb export svg \
        --mode-single \
        --fit-page-to-board \
        --exclude-drawing-sheet \
        --layers F.Cu,F.Mask,F.Silkscreen,F.Fab,Edge.Cuts \
        --output "$out/svg/EveningStar-front.svg" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb export svg \
        --mode-single \
        --fit-page-to-board \
        --exclude-drawing-sheet \
        --mirror \
        --layers B.Cu,B.Mask,B.Silkscreen,B.Fab,Edge.Cuts \
        --output "$out/svg/EveningStar-back.svg" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb export svg \
        --mode-multi \
        --fit-page-to-board \
        --exclude-drawing-sheet \
        --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Fab,B.Fab \
        --common-layers Edge.Cuts \
        --output "$out/svg/layers" \
        "$src/pcb/EveningStar.kicad_pcb"
    '';
  };

  renderPlan = mkKicadDerivation {
    name = "eveningstar-renders-plan";
    build = modelEnvironment + ''
      mkdir -p "$out"
      kicad-cli pcb render \
        --side top --width 3600 --height 2700 --quality high \
        --background opaque --output "$out/top.png" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb render \
        --side bottom --width 3600 --height 2700 --quality high \
        --background opaque --output "$out/bottom.png" \
        "$src/pcb/EveningStar.kicad_pcb"
    '';
  };

  renderSides = mkKicadDerivation {
    name = "eveningstar-renders-sides";
    build = modelEnvironment + ''
      mkdir -p "$out"
      kicad-cli pcb render \
        --side front --width 3600 --height 2400 --quality high \
        --background opaque --output "$out/front.png" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb render \
        --side back --width 3600 --height 2400 --quality high \
        --background opaque --output "$out/back.png" \
        "$src/pcb/EveningStar.kicad_pcb"
    '';
  };

  renderIsometric = mkKicadDerivation {
    name = "eveningstar-renders-isometric";
    build = modelEnvironment + ''
      mkdir -p "$out"
      kicad-cli pcb render \
        --rotate "315,0,45" --width 3600 --height 2700 --quality high \
        --background opaque --output "$out/isometric-front.png" \
        "$src/pcb/EveningStar.kicad_pcb"
      kicad-cli pcb render \
        --rotate "315,0,225" --width 3600 --height 2700 --quality high \
        --background opaque --output "$out/isometric-back.png" \
        "$src/pcb/EveningStar.kicad_pcb"
    '';
  };

  renderTurntable = mkKicadDerivation {
    name = "eveningstar-renders-turntable";
    nativeBuildInputs = [
      pkgs.imagemagick
      pkgs.libwebp
      pkgs.python3
    ];
    build = modelEnvironment + ''
      mkdir -p "$out"
      python3 ${turntableScript} \
        --board "$src/pcb/EveningStar.kicad_pcb" \
        --output "$out"
    '';
  };

  stepModel = mkKicadDerivation {
    name = "eveningstar-step-model";
    build = modelEnvironment + ''
      mkdir -p "$out"
      kicad-cli pcb export step \
        --force --subst-models --include-tracks --include-pads --include-zones \
        --include-silkscreen --include-soldermask \
        --output "$out/EveningStar.step" \
        "$src/pcb/EveningStar.kicad_pcb"
    '';
  };

  glbModel = mkKicadDerivation {
    name = "eveningstar-glb-model";
    nativeBuildInputs = [ (pkgs.lib.getBin pkgs.meshoptimizer) ];
    build = modelEnvironment + ''
      mkdir -p "$out"
      kicad-cli pcb export glb \
        --force --subst-models --include-tracks --include-pads --include-zones \
        --include-silkscreen --include-soldermask \
        --output "$TMPDIR/EveningStar.glb" \
        "$src/pcb/EveningStar.kicad_pcb"
      gltfpack -cc \
        -i "$TMPDIR/EveningStar.glb" \
        -o "$out/EveningStar.glb"
    '';
  };

  productionArtifacts = mkKicadDerivation {
    name = "eveningstar-production-artifacts";
    nativeBuildInputs = [ pkgs.python3 ];
    build = ''
      export LC_ALL=C.UTF-8
      export TZ=UTC
      export PYTHONPATH="${kicadPythonPath}:${pkgs.lib.makeSearchPath pkgs.python3.sitePackages pkgs.kicad.pythonPath}"
      kicad-cli pcb drc \
        --severity-error \
        --severity-warning \
        --schematic-parity \
        --exit-code-violations \
        --format report \
        --output "$TMPDIR/production-drc.rpt" \
        "$src/pcb/EveningStar.kicad_pcb"
      python3 ${productionScript} \
        --board "$src/pcb/EveningStar.kicad_pcb" \
        --output "$out" \
        --toolkit "${fabricationToolkit}"
    '';
  };

  reviewArtifacts = pkgs.runCommand "eveningstar-review-artifacts" { } ''
    mkdir -p "$out/schematic" "$out/board" "$out/renders" "$out/models"
    cp -R ${schematicDocuments}/. "$out/schematic/"
    cp -R ${pcbDocuments}/. "$out/board/"
    cp -R ${renderPlan}/. "$out/renders/"
    cp -R ${renderSides}/. "$out/renders/"
    cp -R ${renderIsometric}/. "$out/renders/"
    cp -R ${stepModel}/. "$out/models/"
    cp -R ${glbModel}/. "$out/models/"
  '';

  artifacts = pkgs.runCommand "eveningstar-publish-artifacts" { } ''
    mkdir -p "$out"
    cp -R ${reviewArtifacts}/. "$out/"
    mkdir -p "$out/production"
    cp -R ${productionArtifacts}/. "$out/production/"
  '';
in
{
  inherit
    artifacts
    glbModel
    pcbDocuments
    productionArtifacts
    reviewArtifacts
    renderIsometric
    renderPlan
    renderSides
    renderTurntable
    schematicDocuments
    stepModel
    ;
}
