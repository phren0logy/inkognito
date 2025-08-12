"""Entry point for Inkognito FastMCP server."""

import sys
import logging
from .server import server

def main():
    """Entry point for FastMCP server."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutting down Inkognito FastMCP server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error running FastMCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()