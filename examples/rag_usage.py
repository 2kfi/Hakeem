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

# Generate a test JWT (this is what the test client uses)
# Alternatively, run: python -c "from core.jwt_auth import create_token; print(create_token('test-user', 'test-device'))"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyIiwiZGV2aWNlX2lkIjoidGVzdC1kZXZpY2UiLCJwZXJtaXNzaW9ucyI6W10sImlhdCI6MTc3OTYyMjA5Ny4yMjA4OSwiZXhwIjoxNzc5NzA4NDk3LjIyMDg5fQ.SFsTF-RxwXcmkcg29LHJQqH11kneVHUhk-YjG8FBZg8"

HEADERS = {"Authorization": f"Bearer {TOKEN}"}


async def list_documents():
    resp = await httpx.get(f"{BASE_URL}/api/v1/documents", headers=HEADERS)
    print(f"List documents: {resp.status_code}")
    for doc in resp.json():
        print(f"  - {doc['filename']} ({doc['chunks']} chunks, status={doc['status']})")
    print()


async def upload_document(filepath: str):
    with open(filepath, "rb") as f:
        resp = await httpx.post(
            f"{BASE_URL}/api/v1/documents/upload",
            headers=HEADERS,
            files={"file": (filepath, f, "text/markdown")},
        )
    print(f"Upload {filepath}: {resp.status_code}")
    if resp.status_code == 201:
        d = resp.json()
        print(f"  id={d['id']}, chunks={d['chunks']}, status={d['status']}")
    else:
        print(f"  error: {resp.text}")
    print()


async def search(query: str, top_k: int = 3):
    resp = await httpx.get(
        f"{BASE_URL}/api/v1/documents/search",
        headers=HEADERS,
        params={"q": query, "top_k": top_k},
    )
    print(f"Search '{query}': {resp.status_code}")
    data = resp.json()
    for r in data.get("results", []):
        print(f"  [{r['score']:.3f}] {r['source_file']}")
        print(f"    {r['content'][:120]}...")
    print()
    return data


async def reindex():
    resp = await httpx.post(f"{BASE_URL}/api/v1/documents/reindex", headers=HEADERS)
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
    await search("How does authentication work?")
    await search("What is the WebSocket protocol?")
    await search("How is Redis used for clustering?")

    # 5. Upload a custom file
    # await upload_document("./my_notes.txt")


if __name__ == "__main__":
    asyncio.run(main())
