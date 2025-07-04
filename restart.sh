#!/bin/bash

git pull

sudo supervisorctl restart sse-mcp-gateway

echo "pulled and restarted sse-mcp-gateway"
