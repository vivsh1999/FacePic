#!/bin/bash
# Rebuild the backend image to ensure dependencies are up to date
docker compose build backend

# Run the processor script inside the backend container
# We use --rm to remove the container after it exits
docker compose run --rm backend python process_images.py --disable-upload
