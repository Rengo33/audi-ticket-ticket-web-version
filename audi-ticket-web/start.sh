#!/bin/bash
set -e

echo "Starting Audi Ticket Bot..."

# Build and start the application
docker-compose up --build

# If docker-compose exits, keep the service alive
sleep infinity
