#!/bin/bash
# Expose the locally running MedAdvice server to the public internet.
# Requires cloudflared: brew install cloudflared
# Run ./run.sh in one terminal, then ./tunnel.sh in another.
PORT="${PORT:-8001}"
echo "Starting Cloudflare quick tunnel -> http://localhost:${PORT}"
echo "Copy the printed https://<random>.trycloudflare.com URL into your browser."
exec cloudflared tunnel --url "http://localhost:${PORT}"
