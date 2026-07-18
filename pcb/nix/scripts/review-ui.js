#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

function walk(root) {
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(root, entry.name);
    return entry.isDirectory() ? walk(file) : [file];
  });
}

function relativeUrl(file, root) {
  return path.relative(root, file).split(path.sep).map(encodeURIComponent).join("/");
}

function friendlyName(relativePath) {
  const parts = relativePath.split(path.sep);
  const section = parts.includes("schematic")
    ? "Schematic"
    : parts.includes("renders")
      ? "3D render"
      : parts.includes("layers")
        ? "PCB layer"
        : "PCB";
  let name = path.basename(relativePath, path.extname(relativePath)).replace(/^EveningStar-/, "");
  const acronyms = new Map([["mcu", "MCU"], ["pcb", "PCB"], ["psu", "PSU"]]);
  const title = name === "EveningStar"
    ? "Overview"
    : name.replaceAll("_", " ").replaceAll("-", " ").split(/\s+/)
      .map((word) => acronyms.get(word.toLowerCase()) || `${word[0].toUpperCase()}${word.slice(1)}`)
      .join(" ");
  return `${section}: ${title}`;
}

function matchingFiles(destinationRoot, sourceRoot, suffixes) {
  const collect = (root) => new Map(
    walk(root)
      .filter((file) => suffixes.has(path.extname(file).toLowerCase()))
      .map((file) => [path.relative(root, file), file]),
  );
  const destination = collect(destinationRoot);
  const source = collect(sourceRoot);
  return [...destination.keys()]
    .filter((relativePath) => source.has(relativePath))
    .sort()
    .map((relativePath) => ({ relativePath, destination: destination.get(relativePath), source: source.get(relativePath) }));
}

function main() {
  if (process.argv.length !== 5) {
    console.error("usage: review-ui.js OUTPUT_DIR DESTINATION_LABEL SOURCE_LABEL");
    process.exit(2);
  }

  const outputRoot = path.resolve(process.argv[2]);
  const destinationLabel = process.argv[3];
  const sourceLabel = process.argv[4];
  const destinationRoot = path.join(outputRoot, "destination");
  const sourceRoot = path.join(outputRoot, "source");

  const assets = matchingFiles(destinationRoot, sourceRoot, new Set([".png", ".svg"]))
    .map((entry) => ({
      name: friendlyName(entry.relativePath),
      kind: "document",
      path: entry.relativePath.split(path.sep).join("/"),
      destination: relativeUrl(entry.destination, outputRoot),
      source: relativeUrl(entry.source, outputRoot),
    }));

  const destinationModel = path.join(destinationRoot, "models", "EveningStar.glb");
  const sourceModel = path.join(sourceRoot, "models", "EveningStar.glb");
  if (fs.existsSync(destinationModel) && fs.existsSync(sourceModel)) {
    assets.push({
      name: "Board: Interactive 3D",
      kind: "model",
      path: "models/EveningStar.glb",
      destination: relativeUrl(destinationModel, outputRoot),
      source: relativeUrl(sourceModel, outputRoot),
    });
  }

  if (assets.length === 0) {
    console.error("error: no matching review views were generated");
    process.exit(1);
  }

  const viewerPath = process.env.EVENINGSTAR_REVIEW_VIEWER;
  if (!viewerPath) {
    console.error("error: EVENINGSTAR_REVIEW_VIEWER is not set");
    process.exit(1);
  }
  const viewerBundle = fs.readFileSync(viewerPath, "utf8").replaceAll("</script", "<\\/script");
  const reviewData = JSON.stringify({ destinationLabel, sourceLabel, assets }).replaceAll("<", "\\u003c");
  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EveningStar hardware review</title>
</head>
<body>
  <script>${viewerBundle}</script>
  <script>EveningStarViewer.mountReview(${reviewData});</script>
</body>
</html>
`;
  fs.writeFileSync(path.join(outputRoot, "index.html"), html);
  console.log(`Generated comparison UI with ${assets.length} matching views.`);
}

main();
