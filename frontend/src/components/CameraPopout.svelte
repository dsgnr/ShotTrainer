<script lang="ts">
  import type { FrameSink } from "../lib/frames/sink";
  import type { CameraState } from "../lib/stores/camera";
  import CameraView from "./CameraView.svelte";

  interface Props {
    open: boolean;
    camera: CameraState;
    frames: FrameSink;
    regionFraction: number;
    manualZero: boolean;
    onclose: () => void;
  }

  let { open, camera, frames, regionFraction, manualZero, onclose }: Props = $props();
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="backdrop"
    role="presentation"
    onclick={onclose}
    onkeydown={(event) => event.key === "Escape" && onclose()}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      class="popout"
      role="dialog"
      aria-modal="true"
      aria-label="Camera"
      tabindex="-1"
      onclick={(event) => event.stopPropagation()}
    >
      <CameraView {camera} {frames} {regionFraction} {manualZero} />
      <button type="button" class="close" onclick={onclose}>Close</button>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.6);
    z-index: 10;
  }

  .popout {
    width: min(80vw, 1024px);
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }

  .close {
    align-self: flex-end;
  }
</style>
