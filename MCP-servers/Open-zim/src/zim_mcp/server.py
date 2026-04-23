import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from fastmcp import FastMCP
from libzim.reader import Archive
from libzim.search import Query, Searcher
from libzim.suggestion import SuggestionSearcher

from .config import ZIM_DATA_PATH, SERVER_HOST, SERVER_PORT

mcp = FastMCP("ZIM File Server")


def get_zim_path(filename: str) -> Path:
    base_path = Path(ZIM_DATA_PATH)
    if not filename.endswith(".zim"):
        filename += ".zim"
    return base_path / filename


@mcp.tool
def list_zim_files() -> list[str]:
    """List all available ZIM files in the data directory."""
    base_path = Path(ZIM_DATA_PATH)
    if not base_path.exists():
        return []
    return [f.name for f in base_path.glob("*.zim")]


@mcp.tool
def get_metadata(zim_file: str) -> dict:
    """Get metadata from a ZIM file (title, creator, description, etc.)."""
    zim_path = get_zim_path(zim_file)
    if not zim_path.exists():
        return {"error": f"ZIM file not found: {zim_file}"}

    try:
        with Archive(zim_path) as archive:
            metadata = {
                "name": zim_file,
                "file_size": zim_path.stat().st_size,
                "title": archive.metadata.get("Title", ""),
                "description": archive.metadata.get("Description", ""),
                "creator": archive.metadata.get("Creator", ""),
                "publisher": archive.metadata.get("Publisher", ""),
                "language": archive.metadata.get("Language", ""),
                "date": archive.metadata.get("Date", ""),
                "tags": archive.metadata.get("Tags", ""),
                "has_index": archive.has_index,
                "has_illustration": archive.has_illustration,
            }
            return {k: v for k, v in metadata.items() if v}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def list_articles(zim_file: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """List all articles/entries in a ZIM file."""
    zim_path = get_zim_path(zim_file)
    if not zim_path.exists():
        return [{"error": f"ZIM file not found: {zim_file}"}]

    try:
        with Archive(zim_path) as archive:
            entries = []
            all_entries = list(archive.iter_all())
            total = len(all_entries)

            for i, entry in enumerate(all_entries):
                if i < offset:
                    continue
                if len(entries) >= limit:
                    break

                entry_data = {
                    "path": entry.path,
                    "title": entry.title,
                }
                if entry.is_redirect:
                    entry_data["redirect"] = True
                    entry_data["redirect_target"] = entry.redirect_target
                entries.append(entry_data)

            return {
                "total": total,
                "offset": offset,
                "limit": limit,
                "entries": entries,
            }
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool
def get_article(zim_file: str, path: str) -> dict:
    """Read an article by its path. Returns content and metadata."""
    zim_path = get_zim_path(zim_file)
    if not zim_path.exists():
        return {"error": f"ZIM file not found: {zim_file}"}

    try:
        with Archive(zim_path) as archive:
            entry = archive.get_entry_by_path(path)
            if not entry:
                return {"error": f"Entry not found: {path}"}

            if entry.is_redirect:
                return {
                    "redirect": True,
                    "target_path": entry.redirect_target,
                    "target_title": entry.redirect_target,
                }

            item = entry.get_item()
            content = item.get_content().tobytes().decode("utf-8", errors="replace")

            return {
                "path": entry.path,
                "title": entry.title,
                "mime_type": item.mimetype,
                "size": item.size,
                "content": content,
            }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def search(zim_file: str, query: str, limit: int = 10) -> dict:
    """Search for content in a ZIM file using full-text search."""
    zim_path = get_zim_path(zim_file)
    if not zim_path.exists():
        return {"error": f"ZIM file not found: {zim_file}"}

    try:
        with Archive(zim_path) as archive:
            if not archive.has_index:
                return {"error": "ZIM file does not have a search index"}

            q = Query().set_query(query)
            searcher = Searcher(archive)
            search = searcher.search(q)

            estimated_matches = search.getEstimatedMatches()
            results = []

            for i in range(min(limit, estimated_matches)):
                result = search.get_result(i)
                results.append(
                    {
                        "path": result.path,
                        "title": result.title,
                        "snippet": result.snippet,
                    }
                )

            return {
                "query": query,
                "estimated_matches": estimated_matches,
                "results": results,
            }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
def get_suggestions(zim_file: str, query: str, limit: int = 10) -> dict:
    """Get search suggestions from a ZIM file."""
    zim_path = get_zim_path(zim_file)
    if not zim_path.exists():
        return {"error": f"ZIM file not found: {zim_file}"}

    try:
        with Archive(zim_path) as archive:
            suggestion_searcher = SuggestionSearcher(archive)
            suggestion = suggestion_searcher.suggest(query)

            estimated_matches = suggestion.getEstimatedMatches()
            suggestions = []

            for i in range(min(limit, estimated_matches)):
                result = suggestion.get_result(i)
                suggestions.append(result.title)

            return {
                "query": query,
                "estimated_matches": estimated_matches,
                "suggestions": suggestions,
            }
    except Exception as e:
        return {"error": str(e)}


@mcp.resource("zim://list")
def list_zim_resource() -> list[str]:
    """Resource that lists available ZIM files."""
    return list_zim_files()


@mcp.resource("zim://metadata/{filename}")
def metadata_resource(filename: str) -> dict:
    """Resource that provides metadata for a specific ZIM file."""
    return get_metadata(filename)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        mcp.app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info",
    )
