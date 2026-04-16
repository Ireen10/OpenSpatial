"""Allow ``python -m openspatial_metadata.viz`` without a console script on PATH."""

from .cli import main

if __name__ == "__main__":
    main()
