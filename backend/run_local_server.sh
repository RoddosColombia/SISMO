#!/bin/bash
echo "Starting RODDOS SISMO Backend..."
echo "URL: http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo ""
python -m uvicorn server:app --reload --port 8000
