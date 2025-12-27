#!/bin/bash
# Run the cleanup script inside the processor container
docker compose run --rm processor python cleanup.py "$@"
