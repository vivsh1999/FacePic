#!/bin/bash
# Run the cleanup script inside the backend container
docker compose run --rm backend python cleanup.py "$@"
