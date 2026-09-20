<script lang="ts">
  import type { CommandSender } from "../lib/app/commands";
  import { NUMBER_RANGES, ROTATIONS, clampPreferences } from "../lib/preferences/form";
  import type { PreferencesState } from "../lib/stores/preferences";
  import type { WireCamera, WireFace, WirePreferences } from "../lib/wire/types";

  interface Props {
    open: boolean;
    preferences: PreferencesState;
    cameras: WireCamera[];
    microphones: string[];
    faces: WireFace[];
    send: CommandSender;
    onclose: () => void;
  }

  let { open, preferences, cameras, microphones, faces, send, onclose }: Props = $props();

  // A draft copy the dialog edits, applied on save and discarded on cancel.
  let draft = $state<WirePreferences | null>(null);

  // Load the draft each time the dialog opens, and start the camera preview.
  $effect(() => {
    if (open && preferences.prefs !== null) {
      draft = { ...preferences.prefs };
      void send({ type: "beginPreview", cameraId: preferences.prefs.cameraId });
    }
  });

  function save(): void {
    if (draft !== null) {
      void send({ type: "setPreferences", prefs: clampPreferences(draft) });
      void send({ type: "endPreview", saved: true });
    }
    onclose();
  }

  function cancel(): void {
    void send({ type: "endPreview", saved: false });
    onclose();
  }

  function previewCamera(cameraId: number | null): void {
    void send({ type: "previewCamera", cameraId });
  }

  function previewImage(control: "brightness" | "contrast", value: number): void {
    void send({ type: "previewImage", control, value });
  }

  function previewTransform(): void {
    if (draft === null) {
      return;
    }
    void send({
      type: "previewTransform",
      rotationDegrees: draft.cameraRotation,
      flipHorizontal: draft.cameraFlipH,
      flipVertical: draft.cameraFlipV,
    });
  }

  function optimise(): void {
    void send({ type: "optimise" });
  }
</script>

{#if open && draft !== null}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="backdrop"
    role="presentation"
    onclick={cancel}
    onkeydown={(event) => event.key === "Escape" && cancel()}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      class="dialog"
      role="dialog"
      aria-modal="true"
      aria-label="Preferences"
      tabindex="-1"
      onclick={(event) => event.stopPropagation()}
    >
      <h2>Preferences</h2>

      <section aria-label="Camera">
        <h3>Camera</h3>
        <label>
          Camera
          <select
            value={draft.cameraId ?? ""}
            onchange={(event) => {
              const raw = event.currentTarget.value;
              draft!.cameraId = raw === "" ? null : Number(raw);
              previewCamera(draft!.cameraId);
            }}
          >
            <option value="">None</option>
            {#each cameras as camera (camera.index)}
              <option value={camera.index}>{camera.name}</option>
            {/each}
          </select>
        </label>
        <label>
          Rotation
          <select bind:value={draft.cameraRotation} onchange={previewTransform}>
            {#each ROTATIONS as degrees (degrees)}
              <option value={degrees}>{degrees}&deg;</option>
            {/each}
          </select>
        </label>
        <label class="checkbox">
          <input type="checkbox" bind:checked={draft.cameraFlipH} onchange={previewTransform} />
          Flip horizontally
        </label>
        <label class="checkbox">
          <input type="checkbox" bind:checked={draft.cameraFlipV} onchange={previewTransform} />
          Flip vertically
        </label>
        <label>
          Brightness
          <input
            type="range"
            min={NUMBER_RANGES.cameraBrightness[0]}
            max={NUMBER_RANGES.cameraBrightness[1]}
            bind:value={draft.cameraBrightness}
            oninput={() => previewImage("brightness", draft!.cameraBrightness)}
          />
        </label>
        <label>
          Contrast
          <input
            type="range"
            step="0.05"
            min={NUMBER_RANGES.cameraContrast[0]}
            max={NUMBER_RANGES.cameraContrast[1]}
            bind:value={draft.cameraContrast}
            oninput={() => previewImage("contrast", draft!.cameraContrast)}
          />
        </label>
        <button type="button" onclick={optimise}>Auto-optimise</button>
        {#if preferences.detectorStatus !== null}
          <p class="detector" data-tone={preferences.detectorStatus.severity}>
            {preferences.detectorStatus.text}
          </p>
        {/if}
      </section>

      <section aria-label="Audio">
        <h3>Audio</h3>
        <label>
          Microphone
          <select bind:value={draft.audioDevice}>
            {#each microphones as device (device)}
              <option value={device}>{device}</option>
            {/each}
          </select>
        </label>
        <label>
          Gain
          <input
            type="range"
            step="0.1"
            min={NUMBER_RANGES.audioGain[0]}
            max={NUMBER_RANGES.audioGain[1]}
            bind:value={draft.audioGain}
          />
        </label>
      </section>

      <section aria-label="Detection">
        <h3>Detection</h3>
        <label>
          Shot threshold
          <input
            type="range"
            step="0.01"
            min={NUMBER_RANGES.shotThreshold[0]}
            max={NUMBER_RANGES.shotThreshold[1]}
            bind:value={draft.shotThreshold}
          />
        </label>
        <label>
          Refractory (ms)
          <input
            type="number"
            min={NUMBER_RANGES.shotRefractoryMs[0]}
            max={NUMBER_RANGES.shotRefractoryMs[1]}
            bind:value={draft.shotRefractoryMs}
          />
        </label>
        <label>
          Pre-shot window (ms)
          <input
            type="number"
            min={NUMBER_RANGES.preShotMs[0]}
            max={NUMBER_RANGES.preShotMs[1]}
            bind:value={draft.preShotMs}
          />
        </label>
        <label>
          Post-shot window (ms)
          <input
            type="number"
            min={NUMBER_RANGES.postShotMs[0]}
            max={NUMBER_RANGES.postShotMs[1]}
            bind:value={draft.postShotMs}
          />
        </label>
        <label>
          Release window (ms)
          <input
            type="number"
            min={NUMBER_RANGES.releaseWindowMs[0]}
            max={NUMBER_RANGES.releaseWindowMs[1]}
            bind:value={draft.releaseWindowMs}
          />
        </label>
      </section>

      <section aria-label="Target">
        <h3>Target</h3>
        <label>
          Target face
          <select bind:value={draft.targetFace}>
            {#each faces as face (face.key)}
              <option value={face.key}>{face.label}</option>
            {/each}
          </select>
        </label>
        <label>
          Shot diameter (mm)
          <input
            type="number"
            step="0.1"
            min={NUMBER_RANGES.shotDiameterMm[0]}
            max={NUMBER_RANGES.shotDiameterMm[1]}
            bind:value={draft.shotDiameterMm}
          />
        </label>
        <label>
          Tracking region
          <input
            type="range"
            step="0.05"
            min={NUMBER_RANGES.trackingRegionFraction[0]}
            max={NUMBER_RANGES.trackingRegionFraction[1]}
            bind:value={draft.trackingRegionFraction}
          />
        </label>
        <label>
          Circle diameter (mm)
          <input
            type="number"
            min={NUMBER_RANGES.circleDiameterMm[0]}
            max={NUMBER_RANGES.circleDiameterMm[1]}
            bind:value={draft.circleDiameterMm}
          />
        </label>
        <label class="checkbox">
          <input type="checkbox" bind:checked={draft.invertTraceHorizontal} />
          Invert trace horizontally
        </label>
        <label class="checkbox">
          <input type="checkbox" bind:checked={draft.invertTraceVertical} />
          Invert trace vertically
        </label>
        <label class="checkbox">
          <input type="checkbox" bind:checked={draft.showHoldZone} />
          Show hold zone
        </label>
      </section>

      <div class="actions">
        <button type="button" onclick={cancel}>Cancel</button>
        <button type="button" class="primary" onclick={save}>Save</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.5);
    z-index: 10;
  }

  .dialog {
    width: min(640px, 92vw);
    max-height: 90vh;
    overflow: auto;
    padding: 20px 24px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }

  h2 {
    margin: 0 0 12px;
    color: var(--text-heading);
  }

  section {
    margin-bottom: 16px;
  }

  h3 {
    margin: 0 0 8px;
    color: var(--text-dim);
    font-size: 12px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 6px;
  }

  label.checkbox {
    justify-content: flex-start;
  }

  select,
  input[type="number"] {
    padding: 4px 6px;
    color: var(--text);
    background: var(--panel-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font: inherit;
  }

  .detector[data-tone="warning"] {
    color: var(--tone-warning);
  }

  .detector[data-tone="success"] {
    color: var(--tone-success);
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
