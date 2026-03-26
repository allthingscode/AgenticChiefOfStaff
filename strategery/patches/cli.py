"""
STRATEGIC CLI PATCH: Durable Commands (ARCH-024)
Goal: Inject /checkpoints and /resume into the interactive CLI.
"""
import functools

from rich.console import Console
from rich.table import Table

from strategery.logic.checkpoint_logic import get_checkpoint_manager
from strategery.patches.base import BasePatch, PatchContext

console = Console()

class CLIPatch(BasePatch):
    """Patches CLI interactive loop to support durable commands."""

    @property
    def name(self) -> str:
        return "CLI"

    required_symbols = ["_read_interactive_input_async"]

    def apply(self, context: PatchContext):
        manager = get_checkpoint_manager(context.storage_root)
        self._patch_interactive_loop(manager, context)

        from strategery.patches.base import PatchResult
        return PatchResult(patch_name=self.name, success=True)

    def _patch_interactive_loop(self, manager, context):
        import nanobot.cli.commands as cli_mod
        original_read = cli_mod._read_interactive_input_async

        @functools.wraps(original_read)
        async def patched_read():
            # This is a bit tricky because the prompt is inside the loop.
            # We wrap the input reader to intercept commands before they go to the bus.
            cmd = await original_read()

            stripped = cmd.strip().lower()
            if stripped == "/checkpoints":
                self._list_checkpoints(manager)
                return "" # Return empty to skip processing by agent

            if stripped.startswith("/resume "):
                thread_id = cmd.strip().split(" ", 1)[1]
                await self._resume_thread(thread_id, manager, cli_mod)
                return ""

            return cmd

        cli_mod._read_interactive_input_async = patched_read

    def _list_checkpoints(self, manager):
        checkpoints = manager.list_resumable()
        if not checkpoints:
            console.print("[yellow]No resumable checkpoints found.[/yellow]")
            return

        table = Table(title="Resumable Checkpoints")
        table.add_column("Thread ID", style="cyan")
        table.add_column("Model", style="green")
        table.add_column("Last Iteration", style="magenta")
        table.add_column("Last Active", style="dim")

        for cp in checkpoints:
            table.add_row(
                cp["thread_id"],
                cp["model"],
                str(cp["latest_iteration"]),
                cp["updated_at"]
            )
        console.print(table)
        console.print("[dim]Use /resume {Thread ID} to restart a session.[/dim]")

    async def _resume_thread(self, thread_id, manager, cli_mod):
        state = manager.load_latest(thread_id)
        if not state:
            console.print(f"[red]Error: Checkpoint not found for {thread_id}[/red]")
            return

        console.print(f"[green]Resuming {thread_id} from iteration {state['iteration']}...[/green]")

        # This requires deep integration with the running AgentLoop.
        # For the CLI, we can't easily "inject" into the existing loop task.
        # INSTEAD: We'll instruct the user on how to properly use it or
        # implement a one-off resume runner.

        console.print("[yellow]Note: Interactive resume is currently in POC. Please use 'nanobot agent --resume {id}' for full stability.[/yellow]")
