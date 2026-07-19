{
  pkgs,
  publishNix,
  productionScript,
  destinationSource,
  sourceSource,
}:

let
  publishFor = source: (import publishNix { inherit pkgs productionScript source; }).artifacts;
  destination = publishFor destinationSource;
  source = publishFor sourceSource;
in
pkgs.runCommand "eveningstar-review-inputs" { } ''
  mkdir -p "$out"
  ln -s ${destination} "$out/destination"
  ln -s ${source} "$out/source"
''
