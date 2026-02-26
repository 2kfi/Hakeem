from fastmcp import FastMCP

mcp = FastMCP("Demo Server 🚀")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers and return the result"""
    return a + b + 12

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=2527)
