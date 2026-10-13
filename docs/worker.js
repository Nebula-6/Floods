importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js");

const SOURCES = ["__init__.py", "macho.py", "debpkg.py", "extras.py", "builder.py", "web.py"];
let pyodide = null;

function post(type, payload, transfer) {
  self.postMessage({ type, payload }, transfer || []);
}

function ensureDir(path) {
  const parts = path.split("/").filter(Boolean);
  let current = "";
  for (const part of parts) {
    current += "/" + part;
    if (!pyodide.FS.analyzePath(current).exists) pyodide.FS.mkdir(current);
  }
}

async function boot() {
  post("status", "Loading Python runtime");
  pyodide = await loadPyodide();
  await pyodide.loadPackage("lzma");
  pyodide.setStdout({ batched: (line) => post("log", line) });
  pyodide.setStderr({ batched: (line) => post("log", line) });
  ensureDir("/app/stackipa");
  for (const name of SOURCES) {
    const response = await fetch(`stackipa/${name}`, { cache: "no-cache" });
    if (!response.ok) throw new Error(`could not load stackipa/${name}`);
    pyodide.FS.writeFile(`/app/stackipa/${name}`, await response.text());
  }
  pyodide.runPython("import sys; sys.path.insert(0, '/app')");
  post("ready");
}

async function stageExtras() {
  const plan = JSON.parse(pyodide.runPython("from stackipa import web; web.extras_plan()"));
  for (const relative of plan.files) {
    const target = `${plan.root}/${relative}`;
    if (pyodide.FS.analyzePath(target).exists) continue;
    ensureDir(target.substring(0, target.lastIndexOf("/")));
    const response = await fetch(`${plan.base}/${relative}`);
    if (!response.ok) throw new Error(`could not download ${relative} (${response.status})`);
    pyodide.FS.writeFile(target, new Uint8Array(await response.arrayBuffer()));
  }
}

async function sha256(buffer) {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function fetchPinned(key, pin, relays) {
  for (const relay of relays) {
    const address = relay.replace("{url}", encodeURIComponent(pin.url));
    const host = new URL(address).host;
    post("status", `Downloading ${pin.label} via ${host}`);
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 60000);
      const response = await fetch(address, { signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const buffer = await response.arrayBuffer();
      clearTimeout(timer);
      if ((await sha256(buffer)) !== pin.sha256) throw new Error("checksum did not match the official release");
      post("log", `${pin.label}: downloaded and verified via ${host}`);
      return new Blob([buffer]);
    } catch (error) {
      post("log", `${pin.label}: ${host} failed (${error.message || error})`);
    }
  }
  throw new Error(`could not download ${pin.label}; choose the .deb file yourself instead`);
}

async function resolveDeb(key, supplied, job) {
  if (!job.include[key]) return null;
  if (supplied) return supplied;
  const response = await fetch("pins.json", { cache: "no-cache" });
  const pins = await response.json();
  const relays = (job.relay ? [job.relay] : []).concat(pins.relays);
  return fetchPinned(key, pins[key], relays);
}

async function build(job) {
  job.eevee = await resolveDeb("eevee", job.eevee, job);
  job.chroma = await resolveDeb("chroma", job.chroma, job);
  ensureDir("/in");
  ensureDir("/out");
  const blobs = [{ name: "spotify.ipa", data: job.ipa }];
  if (job.eevee) blobs.push({ name: "eevee.deb", data: job.eevee });
  if (job.chroma) blobs.push({ name: "chroma.deb", data: job.chroma });
  pyodide.FS.mount(pyodide.FS.filesystems.WORKERFS, { blobs }, "/in");
  try {
    post("status", "Fetching helper frameworks");
    await stageExtras();
    post("status", job.options.dryRun ? "Checking files" : "Building IPA");
    const request = {
      ...job.options,
      ipa: "/in/spotify.ipa",
      eevee: job.eevee ? "/in/eevee.deb" : null,
      chroma: job.chroma ? "/in/chroma.deb" : null,
      output: "/out/result.ipa",
    };
    pyodide.globals.set("job_json", JSON.stringify(request));
    const ok = await pyodide.runPythonAsync("from stackipa import web; web.run(job_json)");
    if (!ok) {
      post("failed");
      return;
    }
    if (job.options.dryRun) {
      post("checked");
      return;
    }
    const data = pyodide.FS.readFile("/out/result.ipa");
    pyodide.FS.unlink("/out/result.ipa");
    post("done", data.buffer, [data.buffer]);
  } finally {
    pyodide.FS.unmount("/in");
  }
}

self.onmessage = async (event) => {
  try {
    if (event.data.type === "build") await build(event.data.job);
  } catch (error) {
    post("log", `error: ${error.message || error}`);
    post("failed");
  }
};

boot().catch((error) => post("fatal", String(error.message || error)));
