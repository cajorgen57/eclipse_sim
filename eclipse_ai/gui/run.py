"""Launch script for Eclipse AI GUI testing tool."""

import uvicorn
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    """Start the GUI server."""
    print("=" * 70)
    print("Eclipse AI GUI Testing Tool")
    print("=" * 70)
    print("\nStarting server...")
    print("Open http://localhost:8000 in your browser")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 70 + "\n")
    
    uvicorn.run(
        "eclipse_ai.gui.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()

