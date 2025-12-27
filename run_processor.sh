#!/bin/bash
# Rebuild the processor image to ensure dependencies are up to date
docker compose build processor

# Run the processor script inside the processor container
# We use --rm to remove the container after it exits
docker compose run --rm processor python process_images.py --disable-upload
