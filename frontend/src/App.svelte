<script lang="ts">
  import AppHeader from "./components/AppHeader.svelte";
  import AppShell from "./components/AppShell.svelte";
  import LiveRegion from "./components/LiveRegion.svelte";
  import StatusLine from "./components/StatusLine.svelte";
  import type { Announcer } from "./lib/app/announcer.svelte";
  import type { Connection } from "./lib/app/connection";
  import { statusLine } from "./lib/app/status-line";
  import type { AppState } from "./lib/stores/app.svelte";

  interface Props {
    app: AppState;
    connection: Connection;
    announcer: Announcer;
  }

  let { app, connection, announcer }: Props = $props();

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
  {#snippet status()}
    <StatusLine {line} {restarting} onrestart={restart} />
  {/snippet}
</AppShell>
<LiveRegion {announcer} />
