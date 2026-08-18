#!/usr/bin/env node
// SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
// Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
// Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
// Version: 6.8.0-beta.1 | Date: 2026-08-18
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, copyFileSync, mkdirSync } from "node:fs";
import { tmpdir, homedir } from "node:os";
import { basename, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
const VERSION = "6.8.0-beta.1";
const args = process.argv.slice(2);
const get = (name, fallback = undefined) => { const i=args.indexOf(name); return i>=0 ? args[i+1] : fallback; };
if ((args[0] || "install") !== "install") { console.error("usage: iot-ai-bootstrap install --package|--url ... --sha256 ... [--apply]"); process.exit(2); }
const expected = get("--sha256", process.env.IOT_AI_RELEASE_SHA256);
if (!expected) { console.error("expected SHA-256 is required"); process.exit(2); }
const home = resolve(get("--home", homedir()));
const store = resolve(get("--package-store", join(home,"ai-iot","Install","MC-GPT")));
const archive = resolve(get("--package-archive", join(home,"ai-iot","Archive","MC-GPT")));
const local = get("--package");
const url = get("--url", process.env.IOT_AI_RELEASE_URL || `https://github.com/IoTAiTech/MC-GPT/releases/download/v${VERSION}/IoT-AI-Tech-iot-ai-Coder-Suite-v${VERSION}-ALL-IN-ONE.zip`);
const temp = mkdtempSync(join(tmpdir(),"iot-ai-npx-"));
try {
  const pkg = join(temp,`IoT-AI-Tech-iot-ai-Coder-Suite-v${VERSION}-ALL-IN-ONE.zip`);
  if (local) copyFileSync(resolve(local),pkg); else {
    const command = process.platform === "win32" ? ["powershell","-NoProfile","-Command",`Invoke-WebRequest -UseBasicParsing -Uri '${url.replaceAll("'","''")}' -OutFile '${pkg.replaceAll("'","''")}'`] : ["curl","--fail","--silent","--show-error","--location",url,"--output",pkg];
    const downloaded=spawnSync(command[0],command.slice(1),{stdio:"inherit"}); if(downloaded.status!==0) process.exit(downloaded.status||4);
  }
  const actual=createHash("sha256").update(readFileSync(pkg)).digest("hex"); if(actual!==expected){console.error("SHA-256 mismatch");process.exit(3);}
  mkdirSync(store,{recursive:true}); mkdirSync(archive,{recursive:true}); const canonical=join(store,basename(pkg)); copyFileSync(pkg,canonical);
  const stage=join(temp,"stage"); mkdirSync(stage);
  const extract = process.platform === "win32" ? spawnSync("powershell",["-NoProfile","-Command",`Expand-Archive -Force -Path '${canonical.replaceAll("'","''")}' -DestinationPath '${stage.replaceAll("'","''")}'`],{stdio:"inherit"}) : spawnSync("unzip",["-q",canonical,"-d",stage],{stdio:"inherit"});
  if(extract.status!==0) process.exit(extract.status||4);
  const apply=args.includes("--apply");
  let run;
  if(process.platform === "win32") {
    const script=join(stage,"installers","Install-IotAiSuite.ps1"); const ps=["-NoProfile","-ExecutionPolicy","Bypass","-File",script,"-HomePath",home,"-PackageStore",store,"-PackageArchive",archive,"-CurrentPackage",canonical]; if(apply) ps.push("-Apply"); run=spawnSync("powershell",ps,{stdio:"inherit"});
  } else {
    const script=join(stage,"installers","install.sh"); const sh=[script,"--home",home,"--package-store",store,"--package-archive",archive,"--current-package",canonical]; if(apply) sh.push("--apply"); run=spawnSync("sh",sh,{stdio:"inherit"});
  }
  process.exit(run.status ?? 1);
} finally { rmSync(temp,{recursive:true,force:true}); }
