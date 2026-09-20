<script lang="ts">
  import AppHeader from "./components/AppHeader.svelte";
  import AppShell from "./components/AppShell.svelte";
  import CameraView from "./components/CameraView.svelte";
  import LiveRegion from "./components/LiveRegion.svelte";
  import HeroStats from "./components/HeroStats.svelte";
  import PreferencesDialog from "./components/PreferencesDialog.svelte";
  import ReplayControls from "./components/ReplayControls.svelte";
  import SessionControls from "./components/SessionControls.svelte";
  import ShotList from "./components/ShotList.svelte";
  import StatusLine from "./components/StatusLine.svelte";
  import TargetView from "./components/TargetView.svelte";
  import ZoomControls from "./components/ZoomControls.svelte";
  import type { Announcer } from "./lib/app/announcer.svelte";
  import type { CommandSender } from "./lib/app/commands";
  import type { Connection } from "./lib/app/connection";
  import { statusLine } from "./lib/app/status-line";
  import type { FrameSink } from "./lib/frames/sink";
  import type { AppState } from "./lib/stores/app.svelte";
  import { DEFAULT_EXTENT_MM, extentForRings } from "./lib/target/geometry";
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
  $effect(() => {
    const loaded = app.replay.loaded;
    if (loaded === null) {
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
    extentMm = extentForRings(rings);
  });
  $effect(() => {
    targetModel.setExtent(extentMm);
  });

  function setExtent(next: number): void {
    extentMm = next;
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

<AppShell>
  {#snippet header()}
    <AppHeader session={app.session.state} trackingText={app.status.trackingText} />
  {/snippet}
  {#snippet camera()}
    <CameraView
      camera={app.camera}
      {frames}
      regionFraction={app.preferences.prefs?.trackingRegionFraction ?? 1}
      manualZero={app.preferences.zero.active}
    />
  {/snippet}
  {#snippet target()}
    <div class="target-column">
      <TargetView model={targetModel} {rings} onextent={setExtent} />
      <ReplayControls replay={app.replay} {send} />
      <ZoomControls {extentMm} onextent={setExtent} />
    </div>
  {/snippet}
  {#snippet side()}
    <button type="button" onclick={() => (preferencesOpen = true)}>Preferences</button>
    <SessionControls session={app.session.state} summary={app.session.summary} {send} />
    <ShotList shots={app.shots.shots} selected={app.shots.selected} {send} />
    <HeroStats
      total={app.shots.totalScore}
      shotCount={app.shots.shots.length}
      group={app.shots.group}
      traceStats={app.shots.holdTrace?.stats ?? null}
      {tracePoints}
      {rings}
    />
  {/snippet}
  {#snippet status()}
    <StatusLine {line} {restarting} onrestart={restart} />
  {/snippet}
</AppShell>

<style>
  .target-column {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
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
<LiveRegion {announcer} />
