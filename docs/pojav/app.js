const $ = (id) => document.getElementById(id);
const worker = new Worker("worker.js?v=1");
let ipa = null;
let ready = false;
let busy = false;
let downloadUrl = null;

function log(line) {
  const box = $("log");
  box.textContent += line + "\n";
  box.scrollTop = box.scrollHeight;
}

function refresh() {
  const usable = ready && !busy && ipa;
  $("check").disabled = !usable;
  $("build").disabled = !usable;
  $("hint").textContent = !ready ? "Waiting for the Python runtime to load." : busy ? "Working." : !ipa ? "Choose the PojavLauncher IPA first." : "";
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

$("ipa").addEventListener("change", (event) => {
  ipa = event.target.files[0] || null;
  $("ipa-name").textContent = ipa ? ipa.name : "Choose file";
  event.target.closest(".pick").classList.toggle("chosen", Boolean(ipa));
  resetDownload();
  refresh();
});

function start(dryRun) {
  resetDownload();
  $("log").textContent = "";
  setBusy(true);
  worker.postMessage({ type: "build", job: { ipa, dryRun } });
}

$("check").addEventListener("click", () => start(true));
$("build").addEventListener("click", () => start(false));

worker.onmessage = (event) => {
  const { type, payload } = event.data;
  if (type === "status") $("status").textContent = payload;
  else if (type === "log") log(payload);
  else if (type === "ready") {
    ready = true;
    $("status").textContent = "Ready. Choose the IPA.";
    refresh();
  } else if (type === "checked") {
    $("status").textContent = "Looks good. Tap Patch IPA.";
    setBusy(false);
  } else if (type === "failed") {
    $("status").textContent = "Stopped. See the log below.";
    setBusy(false);
  } else if (type === "fatal") {
    $("status").textContent = "Could not start: " + payload;
  } else if (type === "done") {
    const blob = new Blob([payload], { type: "application/octet-stream" });
    downloadUrl = URL.createObjectURL(blob);
    const base = ipa.name.replace(/\.(ipa|zip)$/i, "");
    $("download").href = downloadUrl;
    $("download").download = `${base}-authfix.ipa`;
    $("download").hidden = false;
    $("status").textContent = `Done. ${(blob.size / 1048576).toFixed(0)} MB. Tap Download IPA.`;
    setBusy(false);
  }
};
