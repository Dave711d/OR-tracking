import assert from "node:assert/strict";
import { copyFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";

function canvasContext() {
  return new Proxy({}, {
    get(_target, prop) {
      if (prop === "measureText") {
        return (text) => ({ width: String(text).length * 8 });
      }
      if (prop === "getImageData") {
        return () => ({ width: 1, height: 1, data: new Uint8ClampedArray(4) });
      }
      return () => undefined;
    },
    set() {
      return true;
    },
  });
}

function createElement(tagName = "div") {
  return {
    tagName: String(tagName).toUpperCase(),
    children: [],
    classList: {
      add() {},
      contains() { return false; },
      remove() {},
      toggle() {},
    },
    dataset: {},
    style: {},
    hidden: false,
    textContent: "",
    value: "",
    checked: false,
    files: [],
    src: "",
    paused: true,
    ended: false,
    readyState: 0,
    videoHeight: 1,
    videoWidth: 1,
    currentTime: 0,
    width: 320,
    height: 180,
    append(...nodes) {
      this.children.push(...nodes);
    },
    replaceChildren(...nodes) {
      this.children = [...nodes];
    },
    addEventListener() {},
    getBoundingClientRect() {
      return { width: 320, height: 180 };
    },
    getContext() {
      return canvasContext();
    },
    load() {},
    pause() {
      this.paused = true;
    },
    play() {
      this.paused = false;
      return Promise.resolve();
    },
    querySelector() {
      return createElement("span");
    },
    removeAttribute() {},
    setAttribute() {},
  };
}

test("static app module loads with its replay helpers", async () => {
  const previousDocument = globalThis.document;
  const previousWindow = globalThis.window;
  const previousRequestAnimationFrame = globalThis.requestAnimationFrame;
  const previousCancelAnimationFrame = globalThis.cancelAnimationFrame;
  const elements = new Map();
  const tempDir = await mkdtemp(path.join(tmpdir(), "or-tracking-app-load-"));

  globalThis.document = {
    createElement,
    querySelector(selector) {
      if (!elements.has(selector)) {
        elements.set(selector, createElement(selector.includes("Canvas") ? "canvas" : "div"));
      }
      return elements.get(selector);
    },
  };
  globalThis.window = {
    devicePixelRatio: 1,
    addEventListener() {},
  };
  globalThis.requestAnimationFrame = () => 0;
  globalThis.cancelAnimationFrame = () => {};

  try {
    await copyFile(new URL("../public/app.js", import.meta.url), path.join(tempDir, "app.mjs"));
    await copyFile(
      new URL("../public/browser_identity.mjs", import.meta.url),
      path.join(tempDir, "browser_identity.mjs"),
    );
    await copyFile(
      new URL("../public/replay_view.mjs", import.meta.url),
      path.join(tempDir, "replay_view.mjs"),
    );
    await copyFile(
      new URL("../public/case_setup.mjs", import.meta.url),
      path.join(tempDir, "case_setup.mjs"),
    );

    await import(pathToFileURL(path.join(tempDir, "app.mjs")).href);

    assert.equal(elements.get("#hospitalSelect").children.length, 1);
    assert.equal(elements.get("#locationSelect").children.length, 3);
    assert.equal(elements.get("#caseSelect").children.length, 3);
    assert.equal(elements.get("#proceduralistChecklist").children.length, 5);
    assert.equal(elements.get("#caseTaskEditor").children.length, 6);
    assert.equal(elements.get("#initialStage").children.length, 8);
    assert.equal(elements.get("#evaluationDemoSelect").children.length, 6);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
    globalThis.document = previousDocument;
    globalThis.window = previousWindow;
    globalThis.requestAnimationFrame = previousRequestAnimationFrame;
    globalThis.cancelAnimationFrame = previousCancelAnimationFrame;
  }
});
