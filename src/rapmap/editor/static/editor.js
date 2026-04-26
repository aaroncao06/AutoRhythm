(function () {
  "use strict";

  let state = null;
  let wsBacking = null;
  let wsHuman = null;
  let anchorMap = null;
  let beatGrid = null;
  let canonical = null;
  let sampleRate = 48000;
  let selectedIndex = -1;
  let snapEnabled = true;
  let snapStrength = 1.0;

  const gridCanvas = document.getElementById("grid-canvas");
  const gridCtx = gridCanvas.getContext("2d");
  const syllableLayer = document.getElementById("syllable-layer");

  async function init() {
    const resp = await fetch("/api/state");
    state = await resp.json();

    sampleRate = state.sample_rate || 48000;
    anchorMap = state.anchor_map;
    beatGrid = state.beat_grid;
    canonical = state.canonical_syllables;

    if (state.audio_urls.backing) {
      wsBacking = WaveSurfer.create({
        container: "#waveform-backing",
        url: state.audio_urls.backing,
        waveColor: "#555",
        progressColor: "#777",
        height: 120,
        interact: false,
        normalize: true,
      });
    }

    if (state.audio_urls.human) {
      wsHuman = WaveSurfer.create({
        container: "#waveform-human",
        url: state.audio_urls.human,
        waveColor: "#2196F3",
        progressColor: "#64B5F6",
        height: 180,
        normalize: true,
        minPxPerSec: 50,
      });

      wsHuman.on("ready", function () {
        resizeCanvas();
        drawGrid();
        renderBlocks();
        updateInfo();
      });

      wsHuman.on("scroll", function () {
        drawGrid();
        repositionBlocks();
      });

      wsHuman.on("zoom", function () {
        drawGrid();
        repositionBlocks();
      });

      wsHuman.on("timeupdate", function (time) {
        document.getElementById("cursor-time").textContent =
          "Time: " + time.toFixed(3) + "s";
      });
    }

    if (beatGrid && beatGrid.bpm) {
      document.getElementById("bpm-display").textContent =
        "BPM: " + beatGrid.bpm.toFixed(1);
    }

    initToolbar();
  }

  function resizeCanvas() {
    const wrapper = document.getElementById("waveform-human-wrapper");
    gridCanvas.width = wrapper.clientWidth;
    gridCanvas.height = wrapper.clientHeight;
  }

  function getPixelsPerSecond() {
    if (!wsHuman) return 50;
    const wrapper = wsHuman.getWrapper();
    if (!wrapper) return 50;
    const scrollWidth = wrapper.querySelector("div")
      ? wrapper.scrollWidth
      : wrapper.clientWidth;
    const duration = wsHuman.getDuration();
    if (duration <= 0) return 50;
    return scrollWidth / duration;
  }

  function getScrollLeft() {
    if (!wsHuman) return 0;
    const wrapper = wsHuman.getWrapper();
    return wrapper ? wrapper.scrollLeft : 0;
  }

  function sampleToPixel(sample) {
    const pps = getPixelsPerSecond();
    return (sample / sampleRate) * pps - getScrollLeft();
  }

  function pixelToSample(px) {
    const pps = getPixelsPerSecond();
    return Math.round(((px + getScrollLeft()) / pps) * sampleRate);
  }

  function drawGrid() {
    gridCtx.clearRect(0, 0, gridCanvas.width, gridCanvas.height);
    if (!beatGrid) return;

    const beatSet = new Set(beatGrid.beat_samples || []);

    for (let i = 0; i < beatGrid.grid_samples.length; i++) {
      const sample = beatGrid.grid_samples[i];
      const x = sampleToPixel(sample);
      if (x < -1 || x > gridCanvas.width + 1) continue;

      const isBeat = beatSet.has(sample);
      gridCtx.beginPath();
      gridCtx.moveTo(x, 0);
      gridCtx.lineTo(x, gridCanvas.height);
      if (isBeat) {
        gridCtx.strokeStyle = "rgba(245, 166, 35, 0.6)";
        gridCtx.lineWidth = 1.5;
      } else {
        gridCtx.strokeStyle = "rgba(245, 166, 35, 0.2)";
        gridCtx.lineWidth = 0.5;
      }
      gridCtx.stroke();
    }
  }

  function getSyllableText(index) {
    if (
      canonical &&
      canonical.syllables &&
      index < canonical.syllables.length
    ) {
      return canonical.syllables[index].text || canonical.syllables[index].syllable || "";
    }
    return "";
  }

  function renderBlocks() {
    syllableLayer.innerHTML = "";
    if (!anchorMap || !anchorMap.anchors) return;

    anchorMap.anchors.forEach(function (anchor, i) {
      const div = document.createElement("div");
      div.className = "syllable-block";
      div.dataset.index = i;
      div.textContent = getSyllableText(i);
      positionBlock(div, anchor);
      setupDrag(div, i);
      syllableLayer.appendChild(div);
    });
  }

  function positionBlock(div, anchor) {
    const x = sampleToPixel(anchor.guide_start_sample);
    const w = sampleToPixel(anchor.guide_end_sample) - x;
    div.style.transform = "translateX(" + x + "px)";
    div.style.width = Math.max(6, w) + "px";
  }

  function repositionBlocks() {
    if (!anchorMap || !anchorMap.anchors) return;
    const blocks = syllableLayer.querySelectorAll(".syllable-block");
    blocks.forEach(function (div) {
      const i = parseInt(div.dataset.index);
      positionBlock(div, anchorMap.anchors[i]);
    });
  }

  function setupDrag(div, index) {
    let startX = 0;
    let origAnchor = 0;
    let origStart = 0;
    let origEnd = 0;

    function onMouseDown(e) {
      e.preventDefault();
      selectedIndex = index;
      div.classList.add("dragging", "selected");
      document
        .querySelectorAll(".syllable-block.selected")
        .forEach(function (el) {
          if (el !== div) el.classList.remove("selected");
        });

      const anchor = anchorMap.anchors[index];
      startX = e.clientX;
      origAnchor = anchor.guide_anchor_sample;
      origStart = anchor.guide_start_sample;
      origEnd = anchor.guide_end_sample;

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
      updateSelectedInfo(index);
    }

    function onMouseMove(e) {
      const dx = e.clientX - startX;
      const dSamples = pixelToSample(dx + getScrollLeft()) - pixelToSample(getScrollLeft());

      let newAnchor = origAnchor + dSamples;
      let newStart = origStart + dSamples;
      let newEnd = origEnd + dSamples;

      if (snapEnabled && beatGrid) {
        const nearest = findNearestGrid(newAnchor);
        const snapped =
          newAnchor + Math.round((nearest - newAnchor) * snapStrength);
        const snapDelta = snapped - newAnchor;
        newAnchor = snapped;
        newStart += snapDelta;
        newEnd += snapDelta;
      }

      const prev =
        index > 0
          ? anchorMap.anchors[index - 1].guide_anchor_sample
          : -Infinity;
      const next =
        index < anchorMap.anchors.length - 1
          ? anchorMap.anchors[index + 1].guide_anchor_sample
          : Infinity;

      if (newAnchor <= prev) {
        const clampDelta = prev + 1 - newAnchor;
        newAnchor += clampDelta;
        newStart += clampDelta;
        newEnd += clampDelta;
      }
      if (newAnchor >= next) {
        const clampDelta = next - 1 - newAnchor;
        newAnchor += clampDelta;
        newStart += clampDelta;
        newEnd += clampDelta;
      }

      if (newStart < 0) {
        var shift = -newStart;
        newAnchor += shift;
        newStart = 0;
        newEnd += shift;
      }

      const anchor = anchorMap.anchors[index];
      anchor.guide_anchor_sample = newAnchor;
      anchor.guide_start_sample = newStart;
      anchor.guide_end_sample = newEnd;
      anchor.delta_samples = anchor.human_anchor_sample - newAnchor;

      positionBlock(div, anchor);
    }

    function onMouseUp() {
      div.classList.remove("dragging");
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    }

    div.addEventListener("mousedown", onMouseDown);
  }

  function findNearestGrid(sample) {
    if (!beatGrid || !beatGrid.grid_samples.length) return sample;
    let best = beatGrid.grid_samples[0];
    let bestDist = Math.abs(sample - best);
    for (let i = 1; i < beatGrid.grid_samples.length; i++) {
      const d = Math.abs(sample - beatGrid.grid_samples[i]);
      if (d < bestDist) {
        best = beatGrid.grid_samples[i];
        bestDist = d;
      }
      if (beatGrid.grid_samples[i] > sample) break;
    }
    return best;
  }

  function updateInfo() {
    if (anchorMap && anchorMap.anchors) {
      document.getElementById("syl-count").textContent =
        "Syllables: " + anchorMap.anchors.length;
    }
  }

  function updateSelectedInfo(index) {
    const text = getSyllableText(index);
    const anchor = anchorMap.anchors[index];
    document.getElementById("syl-selected").textContent =
      "Selected: " +
      (text || "#" + index) +
      " @ " +
      (anchor.guide_anchor_sample / sampleRate).toFixed(3) +
      "s";
  }

  function initToolbar() {
    document
      .getElementById("btn-audacity")
      .addEventListener("click", function () {
        fetch("/api/focus-audacity", { method: "POST" });
      });

    document
      .getElementById("btn-grab-audio")
      .addEventListener("click", async function () {
        this.disabled = true;
        this.textContent = "Grabbing...";
        const resp = await fetch("/api/grab-audio", { method: "POST" });
        const data = await resp.json();
        this.disabled = false;
        this.textContent = "Grab Audio";
        if (data.ok) {
          showStatus("Exported " + data.tracks_exported + " tracks", "ok");
          window.location.reload();
        } else {
          showStatus(data.error || "Failed", "err");
        }
      });

    document.getElementById("btn-play").addEventListener("click", function () {
      if (wsHuman) wsHuman.play();
      if (wsBacking) wsBacking.play();
    });

    document.getElementById("btn-stop").addEventListener("click", function () {
      if (wsHuman) wsHuman.stop();
      if (wsBacking) wsBacking.stop();
    });

    document.getElementById("btn-save").addEventListener("click", async function () {
      if (!anchorMap) return;
      const resp = await fetch("/api/anchor_map", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(anchorMap),
      });
      const data = await resp.json();
      if (data.ok) {
        showStatus("Saved", "ok");
      } else {
        showStatus(data.error || "Save failed", "err");
      }
    });

    document
      .getElementById("btn-render-apply")
      .addEventListener("click", async function () {
        this.disabled = true;
        this.textContent = "Rendering...";
        const resp = await fetch("/api/render-apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ anchor_map: anchorMap }),
        });
        const data = await resp.json();
        this.disabled = false;
        this.textContent = "Render + Apply";
        if (data.ok) {
          showStatus("Rendered + applied", "ok");
        } else {
          showStatus(data.error || "Render failed", "err");
        }
      });

    document
      .getElementById("snap-toggle")
      .addEventListener("change", function () {
        snapEnabled = this.checked;
      });

    const slider = document.getElementById("strength-slider");
    slider.addEventListener("input", function () {
      snapStrength = parseInt(this.value) / 100;
      document.getElementById("strength-value").textContent =
        this.value + "%";
    });
  }

  function showStatus(msg, cls) {
    const el = document.getElementById("save-status");
    el.textContent = msg;
    el.className = cls;
    setTimeout(function () {
      el.textContent = "";
      el.className = "";
    }, 3000);
  }

  window.addEventListener("resize", function () {
    resizeCanvas();
    drawGrid();
    repositionBlocks();
  });

  init();
})();
