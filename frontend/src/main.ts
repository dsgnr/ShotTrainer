import "./styles/theme.css";
import "./styles/base.css";

import { mount } from "svelte";

import App from "./App.svelte";
import { Announcer } from "./lib/app/announcer.svelte";
import { Connection } from "./lib/app/connection";
import { createBridge } from "./lib/bridge";
import { FrameSink } from "./lib/frames/sink";
import { AppState } from "./lib/stores/app.svelte";

const target = document.getElementById("app");
if (target === null) {
  throw new Error("The page has no #app element");
}

const app = new AppState();
const frames = new FrameSink();
const announcer = new Announcer();
const connection = new Connection(createBridge(), app, frames);

mount(App, { target, props: { app, connection, announcer, frames } });
void connection.start();
