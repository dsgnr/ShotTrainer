<script lang="ts">
  import type { CommandSender } from "../lib/app/commands";
  import { focusTrap } from "../lib/app/focus-trap";
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
      use:focusTrap
      onclick={(event) => event.stopPropagation()}
    >
      <header class="dialog-head">
        <h2>Preferences</h2>
      </header>

      <div class="dialog-body">
        <section class="group" aria-label="Camera">
          <h3 class="panel-title">Camera</h3>
          <div class="fields">
            <label class="field">
              <span class="field-label">Camera</span>
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

            <label class="field">
              <span class="field-label">Rotation</span>
              <select bind:value={draft.cameraRotation} onchange={previewTransform}>
                {#each ROTATIONS as degrees (degrees)}
                  <option value={degrees}>{degrees}&deg;</option>
                {/each}
              </select>
            </label>

            <label class="field slider">
              <span class="field-label">Brightness</span>
              <input
                type="range"
                min={NUMBER_RANGES.cameraBrightness[0]}
                max={NUMBER_RANGES.cameraBrightness[1]}
                bind:value={draft.cameraBrightness}
                oninput={() => previewImage("brightness", draft!.cameraBrightness)}
              />
              <span class="field-value num">{draft.cameraBrightness}</span>
            </label>

            <label class="field slider">
              <span class="field-label">Contrast</span>
              <input
                type="range"
                step="0.05"
                min={NUMBER_RANGES.cameraContrast[0]}
                max={NUMBER_RANGES.cameraContrast[1]}
                bind:value={draft.cameraContrast}
                oninput={() => previewImage("contrast", draft!.cameraContrast)}
              />
              <span class="field-value num">{draft.cameraContrast.toFixed(2)}</span>
            </label>

            <div class="toggles">
              <label class="toggle">
                <input type="checkbox" bind:checked={draft.cameraFlipH} onchange={previewTransform} />
                Flip horizontally
              </label>
              <label class="toggle">
                <input type="checkbox" bind:checked={draft.cameraFlipV} onchange={previewTransform} />
                Flip vertically
              </label>
            </div>

            <div class="optimise">
              <button type="button" onclick={optimise}>Auto-optimise</button>
              {#if preferences.detectorStatus !== null}
                <span class="detector" data-tone={preferences.detectorStatus.severity}>
                  {preferences.detectorStatus.text}
                </span>
              {/if}
            </div>
          </div>
        </section>

        <section class="group" aria-label="Audio">
          <h3 class="panel-title">Audio</h3>
          <div class="fields">
            <label class="field">
              <span class="field-label">Microphone</span>
              <select bind:value={draft.audioDevice}>
                {#each microphones as device (device)}
                  <option value={device}>{device}</option>
                {/each}
              </select>
            </label>
            <label class="field slider">
              <span class="field-label">Gain</span>
              <input
                type="range"
                step="0.1"
                min={NUMBER_RANGES.audioGain[0]}
                max={NUMBER_RANGES.audioGain[1]}
                bind:value={draft.audioGain}
              />
              <span class="field-value num">{draft.audioGain.toFixed(1)}</span>
            </label>
          </div>
        </section>

        <section class="group" aria-label="Detection">
          <h3 class="panel-title">Detection</h3>
          <div class="fields">
            <label class="field slider">
              <span class="field-label">Shot threshold</span>
              <input
                type="range"
                step="0.01"
                min={NUMBER_RANGES.shotThreshold[0]}
                max={NUMBER_RANGES.shotThreshold[1]}
                bind:value={draft.shotThreshold}
              />
              <span class="field-value num">{draft.shotThreshold.toFixed(2)}</span>
            </label>
            <label class="field">
              <span class="field-label">Refractory</span>
              <span class="input-unit">
                <input
                  type="number"
                  min={NUMBER_RANGES.shotRefractoryMs[0]}
                  max={NUMBER_RANGES.shotRefractoryMs[1]}
                  bind:value={draft.shotRefractoryMs}
                />
                <span class="unit">ms</span>
              </span>
            </label>
            <label class="field">
              <span class="field-label">Pre-shot window</span>
              <span class="input-unit">
                <input
                  type="number"
                  min={NUMBER_RANGES.preShotMs[0]}
                  max={NUMBER_RANGES.preShotMs[1]}
                  bind:value={draft.preShotMs}
                />
                <span class="unit">ms</span>
              </span>
            </label>
            <label class="field">
              <span class="field-label">Post-shot window</span>
              <span class="input-unit">
                <input
                  type="number"
                  min={NUMBER_RANGES.postShotMs[0]}
                  max={NUMBER_RANGES.postShotMs[1]}
                  bind:value={draft.postShotMs}
                />
                <span class="unit">ms</span>
              </span>
            </label>
            <label class="field">
              <span class="field-label">Release window</span>
              <span class="input-unit">
                <input
                  type="number"
                  min={NUMBER_RANGES.releaseWindowMs[0]}
                  max={NUMBER_RANGES.releaseWindowMs[1]}
                  bind:value={draft.releaseWindowMs}
                />
                <span class="unit">ms</span>
              </span>
            </label>
          </div>
        </section>

        <section class="group" aria-label="Target">
          <h3 class="panel-title">Target</h3>
          <div class="fields">
            <label class="field">
              <span class="field-label">Target face</span>
              <select bind:value={draft.targetFace}>
                {#each faces as face (face.key)}
                  <option value={face.key}>{face.label}</option>
                {/each}
              </select>
            </label>
            <label class="field">
              <span class="field-label">Shot diameter</span>
              <span class="input-unit">
                <input
                  type="number"
                  step="0.1"
                  min={NUMBER_RANGES.shotDiameterMm[0]}
                  max={NUMBER_RANGES.shotDiameterMm[1]}
                  bind:value={draft.shotDiameterMm}
                />
                <span class="unit">mm</span>
              </span>
            </label>
            <label class="field slider">
              <span class="field-label">Tracking region</span>
              <input
                type="range"
                step="0.05"
                min={NUMBER_RANGES.trackingRegionFraction[0]}
                max={NUMBER_RANGES.trackingRegionFraction[1]}
                bind:value={draft.trackingRegionFraction}
              />
              <span class="field-value num">{Math.round(draft.trackingRegionFraction * 100)}%</span>
            </label>
            <label class="field">
              <span class="field-label">Circle diameter</span>
              <span class="input-unit">
                <input
                  type="number"
                  min={NUMBER_RANGES.circleDiameterMm[0]}
                  max={NUMBER_RANGES.circleDiameterMm[1]}
                  bind:value={draft.circleDiameterMm}
                />
                <span class="unit">mm</span>
              </span>
            </label>
            <div class="toggles">
              <label class="toggle">
                <input type="checkbox" bind:checked={draft.invertTraceHorizontal} />
                Invert trace horizontally
              </label>
              <label class="toggle">
                <input type="checkbox" bind:checked={draft.invertTraceVertical} />
                Invert trace vertically
              </label>
              <label class="toggle">
                <input type="checkbox" bind:checked={draft.showHoldZone} />
                Show hold zone
              </label>
            </div>
          </div>
        </section>
      </div>

      <footer class="dialog-foot">
        <button type="button" onclick={cancel}>Cancel</button>
        <button type="button" class="primary" onclick={save}>Save</button>
      </footer>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: rgba(0, 0, 0, 0.55);
    z-index: 10;
  }

  .dialog {
    display: flex;
    flex-direction: column;
    width: min(560px, 94vw);
    max-height: 88vh;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
  }

  .dialog-head {
    flex: none;
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid var(--divider);
  }

  h2 {
    margin: 0;
    color: var(--text-heading);
    font-size: var(--text-lg);
    font-weight: 600;
  }

  .dialog-body {
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: var(--space-4) var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
  }

  .group {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .fields {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .field {
    display: grid;
    grid-template-columns: 9rem 1fr;
    align-items: center;
    gap: var(--space-3);
    min-height: 28px;
  }

  .field.slider {
    grid-template-columns: 9rem 1fr 3rem;
  }

  .field-label {
    color: var(--text-dim);
    font-size: var(--text-sm);
  }

  .field-value {
    color: var(--text);
    font-size: var(--text-sm);
    text-align: right;
  }

  .field select,
  .field input[type="number"] {
    width: 100%;
  }

  .input-unit {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }

  .input-unit input {
    width: 5rem;
  }

  .unit {
    color: var(--text-muted);
    font-size: var(--text-xs);
  }

  .toggles {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding-top: var(--space-1);
  }

  .toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--text);
    font-size: var(--text-sm);
  }

  .toggle input {
    accent-color: var(--accent-strong);
  }

  .optimise {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-top: var(--space-1);
  }

  .detector {
    font-size: var(--text-xs);
  }

  .detector[data-tone="warning"] {
    color: var(--tone-warning);
  }

  .detector[data-tone="success"] {
    color: var(--tone-success);
  }

  .dialog-foot {
    flex: none;
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-5);
    border-top: 1px solid var(--divider);
  }
</style>
