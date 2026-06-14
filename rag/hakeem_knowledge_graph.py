import asyncio
import logging
from typing import Any, Optional

from rag.schemas import Entity, GraphPath

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase, AsyncGraphDatabase
    from neo4j.exceptions import ServiceUnavailable
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j driver not installed; HakeemKnowledgeGraph disabled")


ENTITY_LABELS = {
    "Drug", "Gene", "Organ", "Disease", "Symptom",
    "Procedure", "Anatomy", "Pathway",
}

RELATION_TYPES = {
    "TREATS", "CAUSES", "METABOLIZED_BY", "INDICATES",
    "CONTRAINDICATES", "SIDE_EFFECT", "DIAGNOSED_BY",
    "ASSOCIATED_WITH", "REGULATES", "EXPRESSED_IN",
}

_LABEL_QUERIES: dict[str, str] = {}
_LABEL_MATCH_QUERIES: dict[str, str] = {}
for _label in ENTITY_LABELS:
    _LABEL_QUERIES[_label] = (
        f"MERGE (e:{_label} {{name: $name}}) SET e.type = $type"
    )
    _LABEL_MATCH_QUERIES[_label] = (
        "MATCH (d:Document {id: $doc_id}), "
        f"(e:{_label} {{name: $name}}) "
        "MERGE (e)-[:MENTIONED_IN]->(d)"
    )
_ENTITY_LABEL = "Entity"
_LABEL_QUERIES[_ENTITY_LABEL] = (
    f"MERGE (e:{_ENTITY_LABEL} {{name: $name}}) SET e.type = $type"
)
_LABEL_MATCH_QUERIES[_ENTITY_LABEL] = (
    "MATCH (d:Document {id: $doc_id}), "
    f"(e:{_ENTITY_LABEL} {{name: $name}}) "
    "MERGE (e)-[:MENTIONED_IN]->(d)"
)


class HakeemKnowledgeGraph:
    def __init__(self, uri: str, user: str, password: str,
                 traversal_depth: int = 2):
        self._uri = uri
        self._user = user
        self._password = password
        self._traversal_depth = traversal_depth
        self._driver: Any = None

    async def initialize(self):
        if not NEO4J_AVAILABLE:
            raise RuntimeError("neo4j driver not installed; "
                               "pip install neo4j")

        try:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
            )
            await self._driver.verify_connectivity()
            logger.info("HakeemKnowledgeGraph connected to %s", self._uri)

            await self._ensure_constraints()
        except ServiceUnavailable as e:
            raise RuntimeError(
                f"Cannot connect to Neo4j at {self._uri}: {e}. "
                "Ensure Neo4j is running (docker compose up neo4j)."
            ) from e

    async def _ensure_constraints(self):
        async with self._driver.session() as session:
            for label in sorted(ENTITY_LABELS):
                try:
                    await session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                        f"REQUIRE n.name IS UNIQUE"
                    )
                except Exception:
                    pass

    async def close(self):
        if self._driver:
            await self._driver.close()

    async def index_document(self, doc_id: str, text: str,
                             domain: str, entities: list[Entity]):
        if not self._driver:
            return

        async with self._driver.session() as session:
            await session.run(
                "MERGE (d:Document {id: $doc_id}) "
                "SET d.text = $text, d.domain = $domain",
                doc_id=doc_id, text=text[:10000], domain=domain,
            )

            for entity in entities:
                label = entity.type.capitalize()
                if label not in ENTITY_LABELS:
                    label = _ENTITY_LABEL
                merge_query = _LABEL_QUERIES[label]
                await session.run(
                    merge_query,
                    name=entity.name, type=entity.type,
                )
                match_query = _LABEL_MATCH_QUERIES[label]
                await session.run(
                    match_query,
                    doc_id=doc_id, name=entity.name,
                )

    async def graph_traversal(self, entities: list[Entity],
                              depth: Optional[int] = None) -> list[GraphPath]:
        if not self._driver or not entities:
            return []

        max_depth = depth or self._traversal_depth
        paths: list[GraphPath] = []

        async with self._driver.session() as session:
            for entity in entities:
                label = entity.type.capitalize()
                if label not in ENTITY_LABELS:
                    label = "Entity"

                try:
                    result = await session.run(
                        f"MATCH path = (start:{label} {{name: $name}})"
                        f"-[*1..{max_depth}]-(connected) "
                        "WHERE NOT connected:Document "
                        "RETURN path LIMIT 20",
                        name=entity.name,
                    )
                    async for record in result:
                        neo_path = record["path"]
                        path_steps = []
                        for segment in neo_path:
                            start_node = segment.start_node
                            end_node = segment.end_node
                            rel_type = segment.type
                            path_steps.append({
                                "source": f"[{start_node['type']}: {start_node['name']}]",
                                "relation": f"[{rel_type}]",
                                "target": f"[{end_node['type']}: {end_node['name']}]",
                            })
                        paths.append(GraphPath(
                            path=path_steps,
                            score=1.0 / (len(path_steps) + 1),
                        ))
                except Exception as e:
                    logger.debug("Graph traversal error for %s: %s",
                                 entity.name, e)

        return paths

    async def format_graph_context(self, paths: list[GraphPath]) -> str:
        if not paths:
            return ""

        sections = ["Knowledge graph pathways:"]
        for i, gp in enumerate(paths[:5], 1):
            steps = " → ".join(
                f"{s['source']} {s['relation']} {s['target']}"
                for s in gp.path
            )
            sections.append(f"  {i}. {steps}")

        return "\n".join(sections)
