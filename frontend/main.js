// Placeholder front end that proves the shell works. It draws camera
// pixels, lists recent controller events and offers a restart after the
// controller stops.
const { invoke, Channel } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

const HEADER_LEN = 32;
const KEPT_EVENTS = 50;

const statusLine = document.getElementById("status");
const restartButton = document.getElementById("restart");
const canvas = document.getElementById("camera");
const frameLine = document.getElementById("frame");
const eventList = document.getElementById("events");
const context = canvas.getContext("2d");
const events = [];

function drawPixels(message) {
  const buffer = message instanceof ArrayBuffer ? message : new Uint8Array(message).buffer;
  const view = new DataView(buffer);
  const width = view.getUint32(0, true);
  const height = view.getUint32(4, true);
  const frameId = view.getBigInt64(8, true);
  const sentAt = view.getFloat64(24, true);
  if (width > 0 && height > 0) {
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    const pixels = new Uint8ClampedArray(buffer, HEADER_LEN, width * height * 4);
    context.putImageData(new ImageData(pixels, width, height), 0, 0);
  }
  const latency = (Date.now() - sentAt).toFixed(1);
  frameLine.textContent = `Frame ${frameId}, ${width} x ${height}, drawn ${latency} ms after sending`;
  invoke("frame_drawn");
}

function onEvent(event) {
  const payload = event.payload;
  if (payload.type === "frame" || payload.type === "audioLevel") {
    return;
  }
  if (payload.type === "message") {
    statusLine.textContent = payload.message.text;
  }
  if (payload.type === "controllerFailed") {
    statusLine.textContent = `The controller stopped: ${payload.reason}`;
    restartButton.hidden = false;
  }
  events.unshift(JSON.stringify(payload));
  events.length = Math.min(events.length, KEPT_EVENTS);
  eventList.textContent = events.join("\n");
}

async function showStatus() {
  const status = await invoke("controller_status");
  const devices = status.fakeDevices ? "fake devices" : "system devices";
  if (status.error) {
    statusLine.textContent = `The controller could not start: ${status.error}`;
  } else if (status.denied.length > 0) {
    statusLine.textContent = `Access refused for the ${status.denied.join(" and ")}. Allow it in the system privacy settings.`;
  } else {
    statusLine.textContent = status.running ? `Running with ${devices}` : "Stopped";
  }
  restartButton.hidden = status.running;
}

async function connect() {
  const channel = new Channel();
  channel.onmessage = drawPixels;
  await invoke("subscribe_frames", { onFrame: channel });
  await invoke("frontend_ready");
}

restartButton.addEventListener("click", async () => {
  try {
    await invoke("restart_controller");
    await connect();
  } catch (error) {
    statusLine.textContent = String(error);
  }
  await showStatus();
});

async function main() {
  await listen("ui-event", onEvent);
  try {
    await connect();
  } catch (error) {
    statusLine.textContent = String(error);
  }
  await showStatus();
}

main();
