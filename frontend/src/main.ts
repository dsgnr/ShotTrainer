import "./styles/theme.css";
import "./styles/base.css";

import { mount } from "svelte";

import App from "./App.svelte";
import { Announcer } from "./lib/app/announcer.svelte";
import { createCommandSender } from "./lib/app/commands";
import { Connection } from "./lib/app/connection";
import { createBridge } from "./lib/bridge";
import { FrameSink } from "./lib/frames/sink";
import { AppState } from "./lib/stores/app.svelte";
import { TargetModel } from "./lib/target/model";

const target = document.getElementById("app");
if (target === null) {
  throw new Error("The page has no #app element");
}

const app = new AppState();
const frames = new FrameSink();
const announcer = new Announcer();
const targetModel = new TargetModel();
const bridge = createBridge();
const connection = new Connection(bridge, app, frames);
const send = createCommandSender(bridge, app);

mount(App, { target, props: { app, connection, announcer, frames, targetModel, send } });
void connection.start();
