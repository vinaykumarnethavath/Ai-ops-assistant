"""
CLI Interface for AI Operations Assistant.
Beautiful terminal experience using Typer and Rich.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich import print as rprint
import asyncio
import json
import sys
import os

# Fix Windows console encoding for emoji support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass  # Ignore if reconfigure not available

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_settings
from utils.logger import setup_logging
from agents.orchestrator import Orchestrator, OrchestratorState
from tools.registry import get_tool_registry

app = typer.Typer(
    name="ai-ops",
    help="AI Operations Assistant - Natural language task execution",
    add_completion=False
)
console = Console(force_terminal=True)


def print_banner():
    """Print welcome banner."""
    console.print(Panel.fit(
        "[bold blue]AI Operations Assistant[/bold blue]\n"
        "[dim]Multi-agent system for natural language tasks[/dim]",
        border_style="blue"
    ))


@app.command()
def run(
    task: str = typer.Argument(..., help="Natural language task to execute"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")
):
    """
    Execute a natural language task.
    
    Examples:
        ai-ops run "Get weather in London"
        ai-ops run "Find top Python repositories about AI"
        ai-ops run "Get tech news headlines and weather in Tokyo" -v
    """
    if not json_output:
        print_banner()
        console.print(f"\n[bold]Task:[/bold] {task}\n")
    
    # Run the task
    asyncio.run(_execute_task(task, verbose, json_output))


async def _execute_task(task: str, verbose: bool, json_output: bool):
    """Execute the task asynchronously."""
    try:
        settings = get_settings()
        setup_logging(settings.log_level if verbose else "WARNING", json_format=False)
        
        orchestrator = Orchestrator()
        
        if not json_output:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                # Track progress through phases
                task_progress = progress.add_task("Planning...", total=None)
                
                async def run_with_progress():
                    result = await orchestrator.run(task)
                    return result
                
                # Create task for the orchestrator
                import asyncio
                orchestrator_task = asyncio.create_task(run_with_progress())
                
                # Poll for state changes
                while not orchestrator_task.done():
                    state = orchestrator.get_state()
                    state_messages = {
                        OrchestratorState.PLANNING: "Planning...",
                        OrchestratorState.EXECUTING: "Executing steps...",
                        OrchestratorState.VERIFYING: "Verifying results...",
                        OrchestratorState.RETRYING: "Retrying failed steps...",
                    }
                    progress.update(task_progress, description=state_messages.get(state, "Processing..."))
                    await asyncio.sleep(0.1)
                
                result = await orchestrator_task
        else:
            result = await orchestrator.run(task)
        
        # Output results
        if json_output:
            output = {
                "status": result.output.status if result.output else "error",
                "result": result.output.model_dump() if result.output else None,
                "error": result.error
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            _print_result(result, verbose)
            
    except Exception as e:
        if json_output:
            print(json.dumps({"status": "error", "error": str(e)}, indent=2))
        else:
            console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _print_result(result, verbose: bool):
    """Print the result in a nice format."""
    console.print()
    
    if result.error:
        console.print(Panel(
            f"[red]Error: {result.error}[/red]",
            title="Failed",
            border_style="red"
        ))
        return
    
    if not result.output:
        console.print("[yellow]No output generated[/yellow]")
        return
    
    output = result.output
    
    # Status badge
    status_colors = {
        "success": "green",
        "partial": "yellow", 
        "failed": "red"
    }
    color = status_colors.get(output.status, "white")
    
    # Summary panel
    status_txt = "SUCCESS" if output.status == 'success' else "PARTIAL" if output.status == 'partial' else "FAILED"
    console.print(Panel(
        f"[{color}]{output.summary}[/{color}]",
        title=f"[{color}]{status_txt}[/{color}] Result",
        border_style=color
    ))
    
    # Data table
    if output.data:
        console.print("\n[bold]Data:[/bold]")
        for key, value in output.data.items():
            if isinstance(value, dict):
                _print_data_section(key, value)
            else:
                console.print(f"  {key}: {value}")
    
    # Execution details (verbose)
    if verbose and output.execution_details:
        console.print("\n[bold]Execution Details:[/bold]")
        details_table = Table(show_header=False, box=None)
        details_table.add_column("Key", style="dim")
        details_table.add_column("Value")
        
        for k, v in output.execution_details.items():
            details_table.add_row(k, str(v))
        
        console.print(details_table)
    
    # Errors
    if output.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in output.errors:
            console.print(f"  - {error}")
    
    console.print()


def _print_data_section(title: str, data: dict):
    """Print a data section nicely."""
    console.print(f"\n  [bold]{title}:[/bold]")
    
    # Handle common data types
    if "repositories" in data:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Repository", style="green")
        table.add_column("Stars", justify="right")
        table.add_column("Language")
        table.add_column("Description", max_width=40)
        
        for repo in data["repositories"][:5]:
            table.add_row(
                repo.get("name", ""),
                f"{repo.get('stars', 0):,}",
                repo.get("language", ""),
                (repo.get("description", "") or "")[:40]
            )
        console.print(table)
        
    elif "articles" in data:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Source", style="green")
        table.add_column("Title", max_width=50)
        
        for article in data["articles"][:5]:
            table.add_row(
                article.get("source", ""),
                (article.get("title", "") or "")[:50]
            )
        console.print(table)
        
    elif "temperature" in data or "city" in data:
        # Weather data
        console.print(f"    City: {data.get('city', 'Unknown')}, {data.get('country', '')}")
        console.print(f"    Temp: {data.get('temperature', 'N/A')}{data.get('unit', 'C')}")
        console.print(f"    Humidity: {data.get('humidity', 'N/A')}%")
        console.print(f"    Condition: {data.get('description', 'N/A')}")
        
    else:
        # Generic dict
        for k, v in list(data.items())[:10]:
            if not isinstance(v, (dict, list)):
                console.print(f"    {k}: {v}")


@app.command()
def tools():
    """List all available tools and their actions."""
    print_banner()
    
    registry = get_tool_registry()
    
    console.print("\n[bold]Available Tools:[/bold]\n")
    
    for tool in registry.get_all():
        console.print(Panel(
            f"[dim]{tool.description}[/dim]\n\n"
            f"[bold]Actions:[/bold] {', '.join(a.name for a in tool.actions)}",
            title=f"[bold green]{tool.name}[/bold green]",
            border_style="green"
        ))


@app.command()
def interactive():
    """Start an interactive session."""
    print_banner()
    console.print("\n[dim]Type your tasks, or 'quit' to exit[/dim]\n")
    
    while True:
        try:
            task = console.input("[bold blue]>>> [/bold blue]")
            
            if task.lower() in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            
            if not task.strip():
                continue
            
            asyncio.run(_execute_task(task, verbose=False, json_output=False))
            
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Goodbye![/dim]")
            break


@app.command()
def version():
    """Show version information."""
    console.print(Panel(
        "[bold]AI Operations Assistant[/bold]\n"
        "Version: 1.0.0\n"
        "Python: " + sys.version.split()[0],
        border_style="blue"
    ))


if __name__ == "__main__":
    app()
