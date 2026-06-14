import logging
from typing import Optional

from rag.schemas import RAGResponse, ScoredChunk

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_WITH_CITATIONS = (
    "You are a precise medical AI assistant. Every clinical claim you make "
    "MUST be followed by a citation in the format [Doc_ID:filename]. "
    "For example: 'Rifaximin is contraindicated in hypersensitivity "
    "[Doc_ID:he_guidelines_2023].' "
    "If you make a claim not supported by the provided context, "
    "do not make it. Respond in the same language as the user."
)


class HakeemCitationFormatter:
    def format_context(self, chunks: list[ScoredChunk],
                       graph_context: str = "") -> str:
        sections: list[str] = []

        for c in chunks[:5]:
            doc_tag = f"[Doc_ID:{c.doc_id}]"
            src = c.filename or c.source_file
            sections.append(
                f"{doc_tag} (source: {src})\n{c.content}"
            )

        if graph_context:
            sections.append(graph_context)

        return "\n\n---\n\n".join(sections)

    def build_system_prompt(self, base_prompt: str = "") -> str:
        if base_prompt:
            return f"{base_prompt}\n\n{_SYSTEM_PROMPT_WITH_CITATIONS}"
        return _SYSTEM_PROMPT_WITH_CITATIONS

    def parse_citations(self, response: str) -> tuple[str, list[str]]:
        import re
        citations = re.findall(r'\[Doc_ID:([^\]]+)\]', response)
        cleaned = re.sub(r'\s*\[Doc_ID:[^\]]+\]', '', response)
        return cleaned, citations

    @staticmethod
    def _format_graph_paths(graph_paths: list) -> str:
        sections = ["Knowledge graph pathways:"]
        for i, gp in enumerate(graph_paths[:5], 1):
            steps = " → ".join(
                f"{s['source']} {s['relation']} {s['target']}"
                for s in gp.path
            )
            sections.append(f"  {i}. {steps}")
        return "\n".join(sections)

    def build_rag_response(self, chunks: list[ScoredChunk],
                            graph_paths: list,
                            verification_status: str,
                            sufficient: bool) -> RAGResponse:
        graph_ctx = self._format_graph_paths(graph_paths) if graph_paths else ""
        formatted = self.format_context(chunks, graph_ctx)
        citations = list(set(
            c.doc_id for c in chunks[:5] if c.doc_id
        ))

        return RAGResponse(
            context="\n\n".join(c.content for c in chunks[:5]),
            formatted_context=formatted,
            chunks=chunks[:5],
            graph_paths=graph_paths,
            domains=list(set(c.domain for c in chunks if c.domain)),
            citations=citations,
            verification_status=verification_status,
            sufficient=sufficient,
        )
