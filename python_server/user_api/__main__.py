"""Run the Python server with Waitress and without the Flask debugger."""

import os

from waitress import serve

from . import create_app

if __name__ == "__main__":
    serve(
        create_app(),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8081")),
        threads=4,
    )
