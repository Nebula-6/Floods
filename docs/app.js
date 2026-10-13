const $ = (id) => document.getElementById(id);
const files = { ipa: null, eevee: null, chroma: null };
const worker = new Worker("worker.js?v=202610131705");
let ready = false;
let busy = false;
let downloadUrl = null;

function log(line) {
  const box = $("log");
  box.textContent += line + "\n";
  box.scrollTop = box.scrollHeight;
}

function included(key) {
  return $(`use-${key}`).checked || Boolean(files[key]);
}

function hint() {
  if (!ready) return "Waiting for the Python runtime to load.";
  if (busy) return "Working. Buttons come back when it finishes.";
  if (!files.ipa) return "Choose your Spotify IPA first.";
  if (!included("eevee") && !included("chroma")) return "Tick Eevee or Chroma, or choose a .deb file under Options.";
  return "";
}

function refresh() {
  const usable = hint() === "";
  $("check").disabled = !usable;
  $("build").disabled = !usable;
  $("hint").textContent = hint();
}

function setBusy(value) {
  busy = value;
  refresh();
}

function resetDownload() {
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl = null;
  $("download").hidden = true;
}

for (const key of Object.keys(files)) {
  $(key).addEventListener("change", (event) => {
    const file = event.target.files[0] || null;
    files[key] = file;
    $(`${key}-name`).textContent = file ? file.name : "Choose file";
    event.target.closest(".pick").classList.toggle("chosen", Boolean(file));
    if (file && key !== "ipa") $(`use-${key}`).checked = true;
    resetDownload();
    refresh();
  });
}

function jobOptions(dryRun) {
  return {
    order: $("order").value.split(","),
    name: $("name").value.trim(),
    bundleId: $("bundle").value.trim(),
    stripExtensions: $("strip").checked,
    sideloadFix: $("target").value === "signed",
    force: $("force").checked,
    dryRun,
    compress: 1,
  };
}

function start(dryRun) {
  resetDownload();
  $("log").textContent = "";
  setBusy(true);
  worker.postMessage({
    type: "build",
    job: {
      ipa: files.ipa,
      eevee: files.eevee,
      chroma: files.chroma,
      include: { eevee: included("eevee"), chroma: included("chroma") },
      relay: $("relay").value.trim(),
      options: jobOptions(dryRun),
    },
  });
}

for (const id of ["use-eevee", "use-chroma"]) $(id).addEventListener("change", refresh);

$("check").addEventListener("click", () => start(true));
$("build").addEventListener("click", () => start(false));

worker.onmessage = (event) => {
  const { type, payload } = event.data;
  if (type === "status") $("status").textContent = payload;
  else if (type === "log") log(payload);
  else if (type === "ready") {
    ready = true;
    $("status").textContent = "Ready. Choose your files.";
    refresh();
  } else if (type === "checked") {
    $("status").textContent = "Files look compatible. Tap Build IPA.";
    setBusy(false);
  } else if (type === "failed") {
    $("status").textContent = "Stopped. See the log below.";
    setBusy(false);
  } else if (type === "fatal") {
    $("status").textContent = "Could not start: " + payload;
  } else if (type === "done") {
    const blob = new Blob([payload], { type: "application/octet-stream" });
    downloadUrl = URL.createObjectURL(blob);
    const base = files.ipa.name.replace(/\.(ipa|zip)$/i, "");
    $("download").href = downloadUrl;
    $("download").download = `${base}-stacked.ipa`;
    $("download").hidden = false;
    $("status").textContent = `Done. ${(blob.size / 1048576).toFixed(0)} MB. Tap Download IPA.`;
    setBusy(false);
  }
};
