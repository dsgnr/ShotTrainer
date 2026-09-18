<script lang="ts">
  import AppHeader from "./components/AppHeader.svelte";
  import AppShell from "./components/AppShell.svelte";
  import CameraView from "./components/CameraView.svelte";
  import LiveRegion from "./components/LiveRegion.svelte";
  import StatusLine from "./components/StatusLine.svelte";
  import TargetView from "./components/TargetView.svelte";
  import ZoomControls from "./components/ZoomControls.svelte";
  import type { Announcer } from "./lib/app/announcer.svelte";
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
  }

  let { app, connection, announcer, frames, targetModel }: Props = $props();

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
      <ZoomControls {extentMm} onextent={setExtent} />
    </div>
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
<LiveRegion {announcer} />
