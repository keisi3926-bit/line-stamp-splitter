"use strict";

const VALID_COUNTS = [8, 16, 24, 32, 40];
const GRID_PRESETS = {
  8: { rows: 2, cols: 4 },
  16: { rows: 4, cols: 4 },
  24: { rows: 4, cols: 6 },
  32: { rows: 4, cols: 8 },
  40: { rows: 5, cols: 8 }
};
const MAX_BYTES = 1024 * 1024;
const state = { mode: "grid", files: [], sourceUrls: [], deferredInstall: null };
const $ = id => document.getElementById(id);

const els = {
  input: $("fileInput"), prompt: $("filePrompt"), summary: $("selectionSummary"), count: $("count"), rows: $("rows"), cols: $("cols"),
  padding: $("padding"), mainIndex: $("mainIndex"), tabIndex: $("tabIndex"), removeWhite: $("removeWhite"), threshold: $("threshold"),
  thresholdRow: $("thresholdRow"), thresholdValue: $("thresholdValue"), preview: $("previewGrid"), generate: $("generateButton"),
  progress: $("progress"), progressBar: $("progress").firstElementChild, result: $("result"), install: $("installButton"), dropZone: $("dropZone")
};

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-tab").forEach(button => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".grid-only").forEach(element => element.hidden = mode !== "grid");
  els.input.multiple = mode === "files";
  els.prompt.textContent = mode === "grid" ? "一覧画像を選択" : "複数の元画像を選択";
  clearSelection();
}

function updateIndexOptions() {
  const count = Number(els.count.value);
  for (const select of [els.mainIndex, els.tabIndex]) {
    const previous = Number(select.value) || 1;
    select.replaceChildren(...Array.from({ length: count }, (_, i) => new Option(`${i + 1}番`, String(i + 1), false, i + 1 === previous)));
  }
}

function applyGridPreset() {
  const preset = GRID_PRESETS[Number(els.count.value)];
  if (!preset) return;
  els.rows.value = String(preset.rows);
  els.cols.value = String(preset.cols);
}

function clearSelection() {
  state.sourceUrls.forEach(URL.revokeObjectURL);
  state.sourceUrls = [];
  state.files = [];
  els.input.value = "";
  els.summary.hidden = true;
  els.preview.innerHTML = '<p class="empty-state">画像を選ぶとプレビューが表示されます</p>';
  els.generate.disabled = true;
  els.result.hidden = true;
}

function receiveFiles(fileList) {
  const files = [...fileList].filter(file => file.type.startsWith("image/"));
  if (!files.length) return showResult("画像ファイルを選択してください。", true);
  state.sourceUrls.forEach(URL.revokeObjectURL);
  state.files = state.mode === "grid" ? files.slice(0, 1) : files;
  state.sourceUrls = state.files.map(URL.createObjectURL);
  els.summary.textContent = state.mode === "grid" ? state.files[0].name : `${state.files.length}枚を選択`;
  els.summary.hidden = false;
  els.generate.disabled = false;
  renderSourcePreviews();
}

function renderSourcePreviews() {
  els.preview.replaceChildren();
  const max = state.mode === "grid" ? 1 : Math.min(state.sourceUrls.length, Number(els.count.value));
  for (let i = 0; i < max; i++) {
    const node = $("previewTemplate").content.cloneNode(true);
    node.querySelector("img").src = state.sourceUrls[i];
    node.querySelector("figcaption").textContent = state.mode === "grid" ? "一覧画像" : String(i + 1).padStart(2, "0");
    els.preview.append(node);
  }
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error(`${file.name}を読み込めませんでした。`)); };
    image.src = url;
  });
}

function imageToCanvas(image, sx = 0, sy = 0, sw = image.naturalWidth, sh = image.naturalHeight) {
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sw)); canvas.height = Math.max(1, Math.round(sh));
  canvas.getContext("2d", { willReadFrequently: true }).drawImage(image, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function removeWhiteAndFindBounds(canvas, removeWhite, threshold) {
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
  let minX = canvas.width, minY = canvas.height, maxX = -1, maxY = -1;
  for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
    const i = (y * canvas.width + x) * 4;
    const isWhite = data.data[i] >= threshold && data.data[i + 1] >= threshold && data.data[i + 2] >= threshold;
    if (removeWhite && data.data[i + 3] && isWhite) data.data[i + 3] = 0;
    if (data.data[i + 3] > 0 && !(removeWhite && isWhite)) { minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y); }
  }
  if (removeWhite) ctx.putImageData(data, 0, 0);
  return maxX < 0 ? { x: 0, y: 0, width: 2, height: 2 } : { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 };
}

function processCanvas(source, options) {
  const bounds = removeWhiteAndFindBounds(source, options.removeWhite, options.threshold);
  const rawW = bounds.width + options.padding * 2, rawH = bounds.height + options.padding * 2;
  const scale = Math.min(370 / rawW, 320 / rawH, 1);
  const width = Math.max(2, Math.floor(rawW * scale) & ~1), height = Math.max(2, Math.floor(rawH * scale) & ~1);
  const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext("2d"); ctx.imageSmoothingQuality = "high";
  ctx.drawImage(source, bounds.x, bounds.y, bounds.width, bounds.height, options.padding * scale, options.padding * scale, bounds.width * scale, bounds.height * scale);
  return canvas;
}

function exactCanvas(source, width, height) {
  const bounds = removeWhiteAndFindBounds(source, false, 255);
  const scale = Math.min(width / bounds.width, height / bounds.height, 1);
  const dw = Math.max(1, Math.floor(bounds.width * scale)), dh = Math.max(1, Math.floor(bounds.height * scale));
  const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
  canvas.getContext("2d").drawImage(source, bounds.x, bounds.y, bounds.width, bounds.height, Math.floor((width - dw) / 2), Math.floor((height - dh) / 2), dw, dh);
  return canvas;
}

function canvasBlob(canvas) { return new Promise((resolve, reject) => canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error("PNG生成に失敗しました。")), "image/png")); }

async function buildStickerCanvases(count, options) {
  if (state.mode === "grid") {
    const image = await loadImage(state.files[0]);
    const rows = Number(els.rows.value), cols = Number(els.cols.value);
    if (rows * cols < count) throw new Error("行数 × 列数がスタンプ数より少なくなっています。");
    return Array.from({ length: count }, (_, i) => processCanvas(imageToCanvas(image, (i % cols) * image.naturalWidth / cols, Math.floor(i / cols) * image.naturalHeight / rows, image.naturalWidth / cols, image.naturalHeight / rows), options));
  }
  if (state.files.length < count) throw new Error(`画像が不足しています。${count}枚必要です。`);
  const canvases = [];
  for (let i = 0; i < count; i++) canvases.push(processCanvas(imageToCanvas(await loadImage(state.files[i])), options));
  return canvases;
}

const crcTable = (() => Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; }))();
function crc32(bytes) { let crc = 0xffffffff; for (const byte of bytes) crc = crcTable[(crc ^ byte) & 255] ^ (crc >>> 8); return (crc ^ 0xffffffff) >>> 0; }
function u16(view, offset, value) { view.setUint16(offset, value, true); }
function u32(view, offset, value) { view.setUint32(offset, value >>> 0, true); }

function createZip(files) {
  const encoder = new TextEncoder(); let offset = 0; const locals = [], centrals = [];
  for (const file of files) {
    const name = encoder.encode(file.name), data = file.data, crc = crc32(data);
    const local = new Uint8Array(30 + name.length + data.length), lv = new DataView(local.buffer);
    u32(lv, 0, 0x04034b50); u16(lv, 4, 20); u16(lv, 6, 0x0800); u16(lv, 8, 0); u32(lv, 14, crc); u32(lv, 18, data.length); u32(lv, 22, data.length); u16(lv, 26, name.length);
    local.set(name, 30); local.set(data, 30 + name.length); locals.push(local);
    const central = new Uint8Array(46 + name.length), cv = new DataView(central.buffer);
    u32(cv, 0, 0x02014b50); u16(cv, 4, 20); u16(cv, 6, 20); u16(cv, 8, 0x0800); u16(cv, 10, 0); u32(cv, 16, crc); u32(cv, 20, data.length); u32(cv, 24, data.length); u16(cv, 28, name.length); u32(cv, 42, offset);
    central.set(name, 46); centrals.push(central); offset += local.length;
  }
  const centralSize = centrals.reduce((sum, item) => sum + item.length, 0), end = new Uint8Array(22), ev = new DataView(end.buffer);
  u32(ev, 0, 0x06054b50); u16(ev, 8, files.length); u16(ev, 10, files.length); u32(ev, 12, centralSize); u32(ev, 16, offset);
  return new Blob([...locals, ...centrals, end], { type: "application/zip" });
}

function download(blob, name) { const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000); }
function showResult(message, error = false) { els.result.textContent = message; els.result.hidden = false; els.result.style.borderColor = error ? "#c54a43" : "#176b5b"; }
function setProgress(value) { els.progress.hidden = false; els.progressBar.style.width = `${value}%`; }

async function generate() {
  const count = Number(els.count.value);
  if (!VALID_COUNTS.includes(count)) return showResult("スタンプ数が正しくありません。", true);
  els.generate.disabled = true; els.result.hidden = true; setProgress(4);
  try {
    const options = { padding: Math.max(0, Number(els.padding.value)), removeWhite: els.removeWhite.checked, threshold: Number(els.threshold.value) };
    const canvases = await buildStickerCanvases(count, options); setProgress(45);
    const output = [], warnings = [];
    for (let i = 0; i < canvases.length; i++) {
      const blob = await canvasBlob(canvases[i]); if (blob.size > MAX_BYTES) warnings.push(`${String(i + 1).padStart(2, "0")}.png: 1MB超過`);
      output.push({ name: `${String(i + 1).padStart(2, "0")}.png`, data: new Uint8Array(await blob.arrayBuffer()) });
      setProgress(45 + Math.round((i + 1) / count * 35));
    }
    for (const [name, canvas] of [["main.png", exactCanvas(canvases[Number(els.mainIndex.value) - 1], 240, 240)], ["tab.png", exactCanvas(canvases[Number(els.tabIndex.value) - 1], 96, 74)]]) {
      const blob = await canvasBlob(canvas); if (blob.size > MAX_BYTES) warnings.push(`${name}: 1MB超過`); output.unshift({ name, data: new Uint8Array(await blob.arrayBuffer()) });
    }
    const report = `LINEスタンプ画像処理レポート\r\n\r\nスタンプ数: ${count}\r\nPNG: OK\r\n最大サイズ: OK\r\nmain.png: 240x240\r\ntab.png: 96x74\r\n1MB超過: ${warnings.length ? warnings.join(", ") : "なし"}\r\n`;
    output.push({ name: "report.txt", data: new TextEncoder().encode(report) }); setProgress(92);
    download(createZip(output), "line_stickers.zip"); setProgress(100);
    showResult(`line_stickers.zip を作成しました。\n${warnings.length ? `警告: ${warnings.join(" / ")}` : "検証エラーはありません。"}`);
  } catch (error) { showResult(error.message || "処理に失敗しました。", true); }
  finally { els.generate.disabled = false; setTimeout(() => { els.progress.hidden = true; }, 800); }
}

document.querySelectorAll(".mode-tab").forEach(button => button.addEventListener("click", () => setMode(button.dataset.mode)));
els.input.addEventListener("change", event => receiveFiles(event.target.files));
els.count.addEventListener("change", () => { applyGridPreset(); updateIndexOptions(); if (state.files.length) renderSourcePreviews(); });
els.removeWhite.addEventListener("change", () => els.thresholdRow.hidden = !els.removeWhite.checked);
els.threshold.addEventListener("input", () => els.thresholdValue.value = els.threshold.value);
els.generate.addEventListener("click", generate);
["dragenter", "dragover"].forEach(type => els.dropZone.addEventListener(type, event => { event.preventDefault(); els.dropZone.classList.add("dragging"); }));
["dragleave", "drop"].forEach(type => els.dropZone.addEventListener(type, event => { event.preventDefault(); els.dropZone.classList.remove("dragging"); }));
els.dropZone.addEventListener("drop", event => receiveFiles(event.dataTransfer.files));
window.addEventListener("beforeinstallprompt", event => { event.preventDefault(); state.deferredInstall = event; els.install.hidden = false; });
els.install.addEventListener("click", async () => { if (!state.deferredInstall) return; state.deferredInstall.prompt(); await state.deferredInstall.userChoice; state.deferredInstall = null; els.install.hidden = true; });
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
applyGridPreset();
updateIndexOptions();
