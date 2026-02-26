from fastmcp import FastMCP
import sqlite3
from pathlib import Path

# =====================================================
# MCP SERVER SETUP
# =====================================================

# Name is simple and descriptive
mcp = FastMCP("Drug Database Lookup")

# Absolute path to SQLite database
DB_PATH = Path(__file__).parent / "db" / "drugs.db"


# =====================================================
# DATABASE HELPER
# =====================================================

def fetch_rows(sql_query: str, parameters: tuple = ()) -> list:
    """
    Execute a SELECT query and return rows as dictionaries.
    """
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()
    cursor.execute(sql_query, parameters)

    rows = cursor.fetchall()
    connection.close()

    # Convert sqlite rows to plain dicts
    return [dict(row) for row in rows]


# =====================================================
# RESULT FORMATTER
# =====================================================

def build_success_response(row: dict, matched_field: str) -> dict:
    """
    Convert database row into MCP response format.
    """
    row["public_id"] = f"{row['id']:05d}"

    return {
        "found": True,
        "matched_by": matched_field,
        "drug": row
    }


def build_not_found_response() -> dict:
    """
    Standard response when nothing is found.
    """
    return {
        "found": False,
        "message": "No drug found"
    }


# =====================================================
# CORE LOOKUP LOGIC
# =====================================================

def lookup_drug_logic(query: str) -> dict:
    """
    Search order (VERY IMPORTANT):
    1) ID
    2) Active ingredient
    3) Generic name
    4) Brand name
    """

    # -----------------------------
    # 1) SEARCH BY ID
    # -----------------------------
    if query.isdigit():
        rows = fetch_rows(
            "SELECT * FROM drugs WHERE id = ?",
            (int(query),)
        )

        if rows:
            return build_success_response(rows[0], "id")

    # Normalize text for comparisons
    normalized_query = query.strip().lower()

    # -----------------------------
    # 2) SEARCH BY ACTIVE INGREDIENT
    # -----------------------------
    rows = fetch_rows(
        "SELECT * FROM drugs WHERE LOWER(active_ingredient) = ?",
        (normalized_query,)
    )

    if rows:
        return build_success_response(rows[0], "active_ingredient")

    # -----------------------------
    # 3) SEARCH BY GENERIC NAME
    # -----------------------------
    rows = fetch_rows(
        "SELECT * FROM drugs WHERE LOWER(generic_name) = ?",
        (normalized_query,)
    )

    if rows:
        return build_success_response(rows[0], "generic_name")

    # -----------------------------
    # 4) SEARCH BY BRAND NAME
    # -----------------------------
    rows = fetch_rows(
        "SELECT * FROM drugs WHERE LOWER(brand_name) = ?",
        (normalized_query,)
    )

    if rows:
        return build_success_response(rows[0], "brand_name")

    # -----------------------------
    # NOTHING FOUND
    # -----------------------------
    return build_not_found_response()


# =====================================================
# MCP TOOL (EXPOSED TO LLM)
# =====================================================

@mcp.tool()
def lookup_drug(query: str) -> dict:
    """
    Look up a drug using a single string input.

    Input:
        query: ID, active ingredient, generic name, or brand name

    Output:
        {
            found: true/false,
            matched_by: field name,
            drug: full drug record (if found)
        }
    """
    return lookup_drug_logic(query)


# =====================================================
# SERVER ENTRY POINT
# =====================================================

if __name__ == "__main__":
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=2528
    )
