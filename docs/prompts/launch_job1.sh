#!/usr/bin/env bash
# Run on thoth from the repo root. Survives SSH disconnect; log in logs/pi_job1.log
set -euo pipefail
cd "$(dirname "$0")/../.."
git fetch origin && git checkout -B pi/m1 origin/main
mkdir -p logs
export LLM=fallback SOURCE=snapshot
nohup claude -p \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit,Glob,Grep,Bash(make:*),Bash(git:*),Bash(python3:*),Bash(python:*),Bash(.venv/bin/*),Bash(pytest:*),Bash(ls:*),Bash(mkdir:*),Bash(cat:*),Bash(head:*),Bash(tail:*),Bash(wc:*)" \
  --max-turns 250 \
  "$(cat docs/prompts/pi_job1.md)" \
  > logs/pi_job1.log 2>&1 &
echo "started pid $! — follow with: tail -f logs/pi_job1.log"
