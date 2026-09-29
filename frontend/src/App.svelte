<script lang="ts">
  import AppShell from "./components/AppShell.svelte";
  import CameraPopout from "./components/CameraPopout.svelte";
  import SessionOverview from "./components/SessionOverview.svelte";
  import LiveRegion from "./components/LiveRegion.svelte";
  import HeroStats from "./components/HeroStats.svelte";
  import MarkerSheet from "./components/MarkerSheet.svelte";
  import NavRail from "./components/NavRail.svelte";
  import PreferencesDialog from "./components/PreferencesDialog.svelte";
  import ReplayControls from "./components/ReplayControls.svelte";
  import SessionBrowser from "./components/SessionBrowser.svelte";
  import SessionSettings from "./components/SessionSettings.svelte";
  import SessionControls from "./components/SessionControls.svelte";
  import ShotList from "./components/ShotList.svelte";
  import StatusLine from "./components/StatusLine.svelte";
  import TargetView from "./components/TargetView.svelte";
  import ZoomControls from "./components/ZoomControls.svelte";
  import type { Announcer } from "./lib/app/announcer.svelte";
  import type { CommandSender } from "./lib/app/commands";
  import type { Connection } from "./lib/app/connection";
  import { resolveShortcut } from "./lib/app/shortcuts";
  import { statusLine } from "./lib/app/status-line";
  import type { FrameSink } from "./lib/frames/sink";
  import type { AppState } from "./lib/stores/app.svelte";
  import { DEFAULT_EXTENT_MM, clampExtent, extentForRings } from "./lib/target/geometry";
  import { sessionViewport } from "./lib/target/session";
  import type { TargetModel } from "./lib/target/model";

  interface Props {
    app: AppState;
    connection: Connection;
    announcer: Announcer;
    frames: FrameSink;
    targetModel: TargetModel;
    send: CommandSender;
  }

  let { app, connection, announcer, frames, targetModel, send }: Props = $props();

  // The target extent follows the rings until the user zooms. A separate
  // reactive value lets the zoom controls and the wheel drive it afterwards.
  let extentMm = $state(DEFAULT_EXTENT_MM);
  let autoZoom = $state(false);

  $effect(() => {
    void app.traceGeneration;
    targetModel.clearTrace();
  });

  $effect(() => {
    targetModel.setShotDiameter(app.preferences.prefs?.shotDiameterMm ?? 4.5);
  });

  // Feed the live aim trace into the model from the camera frames.
  $effect(() => {
    const point = app.camera.frame?.tracePointMm ?? null;
    if (point !== null && point[0] !== null && point[1] !== null) {
      targetModel.appendTracePoint(point[0], point[1]);
    }
  });

  // Keep the shot markers and selection in step with the shots store.
  $effect(() => {
    targetModel.setShots(
      app.shots.shots.map((shot, i) => ({
        xMm: shot.xMm,
        yMm: shot.yMm,
        label: String(i + 1),
      })),
    );
    targetModel.setSelectedShot(app.shots.selected);
  });

  // Reflect a loaded replay in the target: the saved trace, its phase
  // boundaries, the playhead and the hold zone. Clearing it returns the
  // model to the live view.
  const loadedReplay = $derived(app.replay.loaded);
  $effect(() => {
    const loaded = loadedReplay;
    if (loaded === null) {
      targetModel.clearTrace();
      targetModel.setIsolateSelectedShot(false);
      return;
    }
    const points = loaded.points.filter(
      (point): point is [number, number] => point[0] !== null && point[1] !== null,
    );
    targetModel.setIsolateSelectedShot(true);
    targetModel.setTrace(points);
    targetModel.setTraceSegments(loaded.releaseIndex, loaded.splitIndex);
    const zone = loaded.holdZone;
    const centre = zone === null ? null : zone.centreMm;
    const finiteCentre =
      centre !== null && centre[0] !== null && centre[1] !== null
        ? ([centre[0], centre[1]] as [number, number])
        : null;
    targetModel.setHoldZone(finiteCentre, zone?.radiusMm ?? 0);
  });

  $effect(() => {
    targetModel.setPlayhead(app.replay.playhead);
  });

  // Fit the extent to the active face's rings when they arrive.
  const rings = $derived(app.preferences.rings);
  $effect(() => {
    extentMm = clampExtent(extentForRings(rings));
  });
  const automaticViewport = $derived(sessionViewport(
    rings, app.shots.shots, app.preferences.prefs?.shotDiameterMm ?? 4.5,
  ));
  const visibleExtent = $derived(autoZoom ? automaticViewport.extentMm : extentMm);
  const targetCentre = $derived<readonly [number, number]>(autoZoom ? automaticViewport.centre : [0, 0]);
  $effect(() => {
    targetModel.setExtent(visibleExtent);
  });

  function setExtent(next: number): void {
    autoZoom = false;
    extentMm = clampExtent(next);
  }

  // Time-on-target reads the hold trace points when a shot is reviewed.
  const tracePoints = $derived<[number, number][]>(
    (app.shots.holdTrace?.points ?? [])
      .filter((point): point is [number, number] => point[0] !== null && point[1] !== null),
  );

  // Messages expire on the clock, so the line is worked out again as it runs.
  let now = $state(Date.now());
  $effect(() => {
    const timer = setInterval(() => {
      now = Date.now();
    }, 500);
    return () => clearInterval(timer);
  });

  const line = $derived(statusLine(app.status, now));
  const lineText = $derived(line.text);
  $effect(() => {
    announcer.announce(lineText);
  });

  let preferencesOpen = $state(false);
  let page = $state<"target" | "sessions">("target");
  let popoutOpen = $state(false);
  let sheetOpen = $state(false);

  const anyModalOpen = $derived(preferencesOpen || popoutOpen || sheetOpen);

  function closeModals(): void {
    preferencesOpen = false;
    popoutOpen = false;
    sheetOpen = false;
  }

  function isTyping(target: EventTarget | null): boolean {
    return (
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement
    );
  }

  function onKeydown(event: KeyboardEvent): void {
    if (page !== "target" && !anyModalOpen) return;
    const action = resolveShortcut({
      key: event.key,
      typing: isTyping(event.target),
      modalOpen: anyModalOpen,
      replayEnabled: app.replay.loaded?.enabled ?? false,
      replayPlaying: app.replay.playing,
      shotCount: app.shots.shots.length,
      selected: app.shots.selected,
    });
    if (action === null) {
      return;
    }
    event.preventDefault();
    switch (action.kind) {
      case "closeModal":
        closeModals();
        break;
      case "replayToggle":
        void send({ type: action.play ? "replayPlay" : "replayPause" });
        break;
      case "selectShot":
        void send({ type: "selectShot", index: action.index });
        break;
      case "none":
        break;
    }
  }

  $effect(() => {
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  });

  let restarting = $state(false);
  async function restart(): Promise<void> {
    restarting = true;
    try {
      await connection.restart();
    } finally {
      restarting = false;
    }
  }
</script>

{#snippet sessionsPage()}
  <SessionBrowser open={page === "sessions"} sessions={app.session.sessions} {send} onopen={() => page = "target"}
    recording={app.session.state.kind === "recording"}
    onnew={() => { void send({ type: "newSession" }); page = "target"; }} />
{/snippet}
<AppShell page={page === "sessions" ? sessionsPage : undefined}>
  {#snippet nav()}
    <NavRail
      {page}
      ontarget={() => page = "target"}
      onsessions={() => (page = "sessions")}
      onpreferences={() => (preferencesOpen = true)}
      onpopout={() => (popoutOpen = true)}
      onsheet={() => (sheetOpen = true)}
    />
  {/snippet}
  {#snippet shots()}
    <SessionOverview
      shots={app.shots.shots}
      selected={app.shots.selected}
      {rings}
      shotDiameterMm={app.preferences.prefs?.shotDiameterMm ?? 4.5}
      {send}
    />
    <ShotList shots={app.shots.shots} selected={app.shots.selected} {send} />
  {/snippet}
  {#snippet target()}
    <div class="target-column">
      <TargetView model={targetModel} {rings} centre={targetCentre} onextent={setExtent} />
      <div class="target-tools">
        <ReplayControls replay={app.replay} {send} />
        <ZoomControls extentMm={visibleExtent} auto={autoZoom} onauto={() => autoZoom = true}
          referenceExtentMm={extentForRings(rings)} onextent={setExtent} />
      </div>
    </div>
  {/snippet}
  {#snippet side()}
    <HeroStats
      total={app.shots.totalScore}
      shotCount={app.shots.shots.length}
      group={app.shots.group}
      traceStats={app.shots.holdTrace?.stats ?? null}
      {tracePoints}
      {rings}
    />
    <SessionSettings prefs={app.preferences.prefs} faces={app.preferences.faces}
      locked={app.session.state.kind !== "idle" || app.shots.shots.length > 0} {send} />
    <div class="session-footer">
      <SessionControls session={app.session.state} summary={app.session.summary} {send} />
    </div>
  {/snippet}
  {#snippet status()}
    <StatusLine {line} {restarting} onrestart={restart}
      session={app.session.state} trackingText={app.status.trackingText} />
  {/snippet}
</AppShell>

<style>
  .session-footer {
    margin-top: auto;
    flex-shrink: 0;
  }

  .target-column {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }
  .target-tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    border-top: 1px solid var(--divider);
    background: var(--bg-sunken);
  }
</style>
<PreferencesDialog
  open={preferencesOpen}
  preferences={app.preferences}
  cameras={app.devices.cameras}
  microphones={app.devices.microphones}
  faces={app.preferences.faces}
  {send}
  onclose={() => (preferencesOpen = false)}
/>
<CameraPopout
  open={popoutOpen}
  camera={app.camera}
  {frames}
  regionFraction={app.preferences.prefs?.trackingRegionFraction ?? 1}
  manualZero={app.preferences.zero.active}
  onclose={() => (popoutOpen = false)}
/>
<MarkerSheet
  open={sheetOpen}
  shots={app.shots.shots}
  session={app.session.state}
  totalScore={app.shots.totalScore}
  onclose={() => (sheetOpen = false)}
/>
<LiveRegion {announcer} />
