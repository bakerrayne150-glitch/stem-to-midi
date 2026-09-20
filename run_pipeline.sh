#!/bin/bash
# run_pipeline.sh — run the Phase B pipeline with timestamps + peak RSS sampling
cd ~/workspace/stem-to-midi
rm -rf mix_out
START=$(date +%s)
stdbuf -oL -eL ./venv/bin/python full_mix_to_midi.py mix.wav -o mix_out/ > /tmp/pipeline.log 2>&1 &
PID=$!
PEAK=0
while kill -0 $PID 2>/dev/null; do
    RSS=$(awk '/VmHWM/ {print $2}' /proc/$PID/status 2>/dev/null)
    if [ -n "$RSS" ] && [ "$RSS" -gt "$PEAK" ]; then PEAK=$RSS; fi
    sleep 5
done
wait $PID
CODE=$?
END=$(date +%s)
echo "exit=$CODE wall=$((END-START))s peak_rss_kb=$PEAK"
