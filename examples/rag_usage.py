# Arkan Fakoseh -  @2kfi on github
"""
Example: Using Hakeem's RAG API to index and search documents.

Prerequisites:
  1. Start the server: python app.py
  2. Set rag.enabled: true in config.yaml
  3. Get a JWT token (see below)
"""

import asyncio
import httpx

BASE_URL = "http://localhost:8080"

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyIiwiZGV2aWNlX2lkIjoidGVzdC1kZXZpY2UiLCJwZXJtaXNzaW9ucyI6W10sImlhdCI6MTc3OTYyMjA5Ny4yMjA4OSwiZXhwIjoxNzc5NzA4NDk3LjIyMDg5fQ.SFsTF-RxwXcmkcg29LHJQqH11kneVHUhk-YjG8FBZg8"

HEADERS = {"Authorization": f"Bearer {TOKEN}"}


async def list_documents():
    resp = await httpx.get(f"{BASE_URL}/api/v1/rag/documents", headers=HEADERS)
    print(f"List documents: {resp.status_code}")
    data = resp.json()
    for doc in data.get("documents", []):
        print(f"  - {doc['filename']} ({doc['chunks']} chunks, domain={doc.get('domain', '?')})")
    print()


async def upload_document(filepath: str, domain: str = "hepatology"):
    with open(filepath, "rb") as f:
        resp = await httpx.post(
            f"{BASE_URL}/api/v1/rag/documents/upload?domain={domain}",
            headers=HEADERS,
            files={"file": (filepath, f, "text/markdown")},
        )
    print(f"Upload {filepath} -> {domain}: {resp.status_code}")
    if resp.status_code == 200:
        d = resp.json()
        print(f"  doc_id={d['doc_id']}, chunks={d['chunks']}, status={d['status']}")
    else:
        print(f"  error: {resp.text}")
    print()


async def search(query: str):
    resp = await httpx.get(
        f"{BASE_URL}/api/v1/rag/documents/search",
        headers=HEADERS,
        params={"q": query},
    )
    print(f"Search '{query}': {resp.status_code}")
    data = resp.json()
    for r in data.get("results", []):
        print(f"  [{r['score']:.3f}] [{r['domain']}] {r['filename']}")
        print(f"    {r['content'][:120]}...")
    print(f"  sufficient={data.get('sufficient')}, verification={data.get('verification')}")
    print()
    return data


async def reindex():
    resp = await httpx.post(f"{BASE_URL}/api/v1/rag/documents/reindex", headers=HEADERS)
    print(f"Reindex: {resp.status_code}")
    print(f"  {resp.json()}")
    print()


async def main():
    print("=== Hakeem RAG API Examples ===\n")

    # 1. List currently indexed documents
    await list_documents()

    # 2. Reindex configured source directories
    await reindex()

    # 3. List after reindex
    await list_documents()

    # 4. Search
    await search("What are the contraindications of rifaximin?")
    await search("How is dialysis monitored in CKD patients?")

    # 5. Upload a custom file to a specific domain
    # await upload_document("./my_notes.txt", domain="hepatology")


if __name__ == "__main__":
    asyncio.run(main())
