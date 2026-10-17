importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.js");

const SOURCES = ["__init__.py", "macho.py", "debpkg.py", "extras.py", "builder.py", "web.py"];
let pyodide = null;

function post(type, payload, transfer) {
  self.postMessage({ type, payload }, transfer || []);
}

function ensureDir(path) {
  let current = "";
  for (const part of path.split("/").filter(Boolean)) {
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
    const response = await fetch(`../stackipa/${name}`, { cache: "no-cache" });
    if (!response.ok) throw new Error(`could not load stackipa/${name}`);
    pyodide.FS.writeFile(`/app/stackipa/${name}`, await response.text());
  }
  pyodide.runPython("import sys; sys.path.insert(0, '/app')");
  post("ready");
}

async function build(job) {
  const fix = await fetch("PojavAuthFix.dylib", { cache: "no-cache" });
  if (!fix.ok) throw new Error("the fix library is not published yet");
  ensureDir("/in");
  ensureDir("/out");
  pyodide.FS.mount(
    pyodide.FS.filesystems.WORKERFS,
    { blobs: [{ name: "app.ipa", data: job.ipa }, { name: "PojavAuthFix.dylib", data: new Blob([await fix.arrayBuffer()]) }] },
    "/in"
  );
  try {
    post("status", job.dryRun ? "Checking file" : "Patching IPA");
    pyodide.globals.set("job_json", JSON.stringify({
      ipa: "/in/app.ipa",
      output: "/out/result.ipa",
      extraDylibs: ["/in/PojavAuthFix.dylib"],
      dryRun: job.dryRun,
      compress: 1,
    }));
    const ok = await pyodide.runPythonAsync("from stackipa import web; web.run(job_json)");
    if (!ok) {
      post("failed");
      return;
    }
    if (job.dryRun) {
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
