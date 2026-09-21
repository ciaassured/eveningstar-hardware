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

  # One PNG per frame, rendered with Cycles from the board GLB. Only the
  # script's progress lines are passed on from Blender's output.
  turntableFrames = pkgs.runCommand "eveningstar-turntable-frames" {
    nativeBuildInputs = [ pkgs.blender ];
  } ''
    export HOME="$TMPDIR"
    set -o pipefail
    blender -b --factory-startup --python-exit-code 1 \
      -P ${turntableScript} -- \
      --model ${boardGlb}/EveningStar.glb \
      --output "$out" \
      | grep --line-buffered '^turntable:'
  '';

  # 33 ms is the closest WebP frame duration to 30 fps. Method 6 took around
  # forty times longer than method 4 on one core for about 4% smaller output at
  # the same measured quality.
  renderTurntable = pkgs.runCommand "eveningstar-renders-turntable" {
    nativeBuildInputs = [ pkgs.libwebp ];
  } ''
    mkdir -p "$out"
    img2webp -loop 0 -d 33 -lossy -q 65 -m 4 \
      ${turntableFrames}/*.png \
      -o "$out/EveningStar-turntable.webp"
  '';

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

  # The board as fitted, without do-not-populate parts, uncompressed so that
  # both the browser model and the turntable render can build on it.
  boardGlb = mkKicadDerivation {
    name = "eveningstar-board-glb";
    build = modelEnvironment + ''
      mkdir -p "$out"
      kicad-cli pcb export glb \
        --force --subst-models --no-dnp --include-tracks --include-pads \
        --include-zones --include-silkscreen --include-soldermask \
        --output "$out/EveningStar.glb" \
        "$src/pcb/EveningStar.kicad_pcb"
    '';
  };

  glbModel = pkgs.runCommand "eveningstar-glb-model" {
    nativeBuildInputs = [ (pkgs.lib.getBin pkgs.meshoptimizer) ];
  } ''
    mkdir -p "$out"
    gltfpack -cc -i ${boardGlb}/EveningStar.glb -o "$out/EveningStar.glb"
  '';

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
        --schematic "$src/pcb/EveningStar.kicad_sch" \
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

  # Exactly the GitHub release assets, flat because releases hold no folders.
  # Names carry no version so releases/latest/download/<name> always links the
  # newest board; the README embeds the turntable that way.
  artifacts = pkgs.runCommand "eveningstar-publish-artifacts" {
    nativeBuildInputs = [
      pkgs.qpdf
      pkgs.zip
    ];
  } ''
    mkdir -p "$out"

    cp ${productionArtifacts}/EveningStar.zip "$out/EveningStar-gerbers.zip"
    cp ${productionArtifacts}/bom.csv "$out/EveningStar-bom.csv"
    cp ${productionArtifacts}/positions.csv "$out/EveningStar-cpl.csv"
    cp ${productionArtifacts}/netlist.ipc "$out/EveningStar-netlist.ipc"

    cp ${schematicDocuments}/EveningStar-schematic.pdf "$out/"
    qpdf --deterministic-id --empty --pages \
      ${pcbDocuments}/pdf/EveningStar-front.pdf \
      ${pcbDocuments}/pdf/EveningStar-back.pdf \
      ${pcbDocuments}/pdf/EveningStar-layers.pdf \
      -- "$out/EveningStar-board.pdf"

    # Zipped straight from the store so the entry keeps the store's fixed
    # timestamp, and without extra attributes, for a reproducible archive.
    (cd ${stepModel} && zip -X -9 -q "$out/EveningStar-step.zip" EveningStar.step)
    cp ${glbModel}/EveningStar.glb "$out/"

    cp ${renderPlan}/top.png "$out/EveningStar-render-top.png"
    cp ${renderPlan}/bottom.png "$out/EveningStar-render-bottom.png"
    cp ${renderSides}/front.png "$out/EveningStar-render-front.png"
    cp ${renderSides}/back.png "$out/EveningStar-render-back.png"
    cp ${renderIsometric}/isometric-front.png "$out/EveningStar-render-isometric-front.png"
    cp ${renderIsometric}/isometric-back.png "$out/EveningStar-render-isometric-back.png"
    cp ${renderTurntable}/EveningStar-turntable.webp "$out/"

    export LC_ALL=C
    (cd "$out" && sha256sum -- * > SHA256SUMS)
  '';
in
{
  inherit
    artifacts
    boardGlb
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
    turntableFrames
    ;
}
