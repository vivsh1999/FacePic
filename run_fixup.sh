#!/bin/bash
# Run the fixup script inside the processor container
# We mount the script and the app code dynamically so we use the latest changes
docker compose run --rm \
  -v "$(pwd)/processor/fixup.py:/app/fixup.py" \
  -v "$(pwd)/processor/app:/app/app" \
  processor python fixup.py "$@"
