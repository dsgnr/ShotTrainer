<script lang="ts">
  import { onMount } from "svelte";

  import { drawOverlay } from "../lib/camera/overlay";
  import { statusBadge } from "../lib/camera/status";
  import type { FramePacket } from "../lib/frames/packet";
  import type { FrameSink } from "../lib/frames/sink";
  import type { CameraState } from "../lib/stores/camera";

  interface Props {
    camera: CameraState;
    frames: FrameSink;
    /** `trackingRegionFraction` from the preferences. */
    regionFraction: number;
    /** Whether a zero offset is saved. */
    manualZero: boolean;
  }

  let { camera, frames, regionFraction, manualZero }: Props = $props();

  let video: HTMLCanvasElement;
  let overlay: HTMLCanvasElement;
  let width = $state(0);
  let height = $state(0);
  let hasPixels = $state(false);

  function drawPixels(packet: FramePacket): void {
    if (video.width !== packet.width || video.height !== packet.height) {
      video.width = packet.width;
      video.height = packet.height;
    }
    video.getContext("2d")?.putImageData(new ImageData(packet.pixels, packet.width, packet.height), 0, 0);
    hasPixels = true;
  }

  onMount(() => frames.attach(drawPixels));

  $effect(() => {
    if (camera.idle) {
      video.getContext("2d")?.clearRect(0, 0, video.width, video.height);
      hasPixels = false;
    }
  });

  $effect(() => {
    const ratio = window.devicePixelRatio || 1;
    const pixelWidth = Math.round(width * ratio);
    const pixelHeight = Math.round(height * ratio);
    if (overlay.width !== pixelWidth || overlay.height !== pixelHeight) {
      overlay.width = pixelWidth;
      overlay.height = pixelHeight;
    }
    const context = overlay.getContext("2d");
    if (context === null) {
      return;
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    if (hasPixels && camera.frame !== null) {
      drawOverlay(context, width, height, camera.frame, regionFraction);
    }
  });

  const badge = $derived(statusBadge(camera));
</script>

<div class="camera" role="group" aria-label="Camera view" bind:clientWidth={width} bind:clientHeight={height}>
  <canvas bind:this={video} class="video" aria-hidden="true"></canvas>
  <canvas bind:this={overlay} class="overlay" aria-hidden="true"></canvas>
  {#if !hasPixels}
    <p class="empty">No camera</p>
  {/if}
  {#if badge !== null}
    <p class="badge top">
      <span class="dot" style:background={badge.colour}></span>{badge.label}
    </p>
  {/if}
  {#if manualZero}
    <p class="badge bottom"><span class="dot zero"></span>Manual zero</p>
  {/if}
</div>

<style>
  .camera {
    position: relative;
    width: 100%;
    aspect-ratio: 4 / 3;
    background: #000000;
    border-radius: var(--radius);
    overflow: hidden;
  }

  canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .video {
    object-fit: contain;
  }

  .empty {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    margin: 0;
    color: #ffffff;
  }

  .badge {
    position: absolute;
    left: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    padding: 2px 8px 2px 6px;
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.63);
    color: #f7f7f5;
  }

  .top {
    top: 8px;
  }

  .bottom {
    bottom: 8px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .zero {
    background: #ff1493;
  }
</style>
