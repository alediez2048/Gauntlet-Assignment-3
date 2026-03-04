"""LegacyLens CLI entrypoint and query command wiring."""

from __future__ import annotations

from collections.abc import Iterator

import click
from rich.console import Console

from src.api.client import (
    ApiClientHTTPError,
    ApiClientResponseError,
    ApiClientTransportError,
    ApiClientValidationError,
    QueryRequestPayload,
    post_query,
    stream_query,
)
from src.types.responses import QueryResponse, RetrievedChunk

console = Console(highlight=False, markup=False)


def _render_citations(chunks: list[RetrievedChunk]) -> None:
    if not chunks:
        return
    console.print("Citations:")
    for chunk in chunks:
        console.print(f"- {chunk.file_path}:{chunk.line_start}-{chunk.line_end}")


def _render_query_response(response: QueryResponse) -> None:
    console.print(response.answer)
    console.print("")
    console.print(f"Confidence: {response.confidence.value}")
    if response.model:
        console.print(f"Model: {response.model}")
    console.print(f"Latency: {response.latency_ms:.1f}ms")
    if response.codebase_filter:
        console.print(f"Codebase: {response.codebase_filter}")
    _render_citations(response.chunks)


def _render_stream(tokens: Iterator[str]) -> None:
    for token in tokens:
        console.print(token, end="")
    console.print("")


@click.group()
def cli() -> None:
    """LegacyLens command line interface."""


@cli.command("query")
@click.argument("query_text")
@click.option(
    "--feature",
    type=click.STRING,
    default="code_explanation",
    show_default=True,
    help="Code understanding feature to run.",
)
@click.option(
    "--codebase",
    type=click.STRING,
    default=None,
    help="Optional codebase filter.",
)
@click.option(
    "--top-k",
    "top_k",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Number of retrieved chunks to request.",
)
@click.option(
    "--language",
    type=click.STRING,
    default="cobol",
    show_default=True,
    help="Language hint for generation.",
)
@click.option(
    "--model",
    type=click.STRING,
    default=None,
    help="Optional LLM model override.",
)
@click.option(
    "--stream",
    "use_stream",
    is_flag=True,
    default=False,
    help="Use /api/stream endpoint and print tokens as they arrive.",
)
def query_command(
    query_text: str,
    feature: str,
    codebase: str | None,
    top_k: int,
    language: str,
    model: str | None,
    use_stream: bool,
) -> None:
    """Send a query to FastAPI backend and render the response."""
    payload = QueryRequestPayload(
        query=query_text,
        feature=feature,
        codebase=codebase,
        top_k=top_k,
        language=language,
        model=model,
    )

    try:
        if use_stream:
            _render_stream(stream_query(payload))
            return

        response = post_query(payload)
        _render_query_response(response)
    except ApiClientValidationError as exc:
        raise click.UsageError(str(exc)) from exc
    except ApiClientTransportError as exc:
        raise click.ClickException(f"Transport error: {exc}") from exc
    except ApiClientHTTPError as exc:
        raise click.ClickException(
            f"API request failed ({exc.status_code}): {exc.detail}"
        ) from exc
    except ApiClientResponseError as exc:
        raise click.ClickException(f"Invalid API response: {exc}") from exc


if __name__ == "__main__":
    cli()
