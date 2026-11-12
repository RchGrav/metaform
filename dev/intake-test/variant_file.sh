#!/bin/bash
# usage: variant_file.sh <procedure file> <label> <runs>   (records in line into a file)
T=/tmp/claude-1000/-home-rich-metaform/adfc5f6a-d5c7-4dfe-88d2-e0b87bbededd/scratchpad/phototest; S=/tmp/claude-1000/-home-rich-metaform/adfc5f6a-d5c7-4dfe-88d2-e0b87bbededd/scratchpad; f=$1; L=$2; N=$3; mkdir -p $T/v/$L
for i in $(seq 1 $N); do mkdir -p $T/rec-$L/$i; rm -f $T/rec-$L/$i/*
python3 - "$f" "$T/v/$L/prompt-$i.txt" "file://$T/n/photos/" "$T/rec-$L/$i/record.jsonl" <<'PY'
import sys
s=open(sys.argv[1],encoding="utf-8").read(); assert s.count("{prompt}")==1
open(sys.argv[2],"w",encoding="utf-8").write(s.replace("{prompt}",sys.argv[3])+"\nThis is a procedure test. No intake tool is connected. Use the file %s as the record: add each object to it with the Write and Edit tools at the moment the procedure says to record it. Finish by returning the complete map to me in JSON.\n" % sys.argv[4])
PY
done
cp $T/v/$L/prompt-1.txt $T/v/$L/prompt.txt
cd $T/n/photos; for i in $(seq 1 $N); do (claude -p --model sonnet --setting-sources "" --strict-mcp-config --tools "Read,Glob,Write,Edit" --allowedTools "Read,Glob,Write,Edit" --add-dir $T/rec-$L/$i --permission-mode dontAsk --output-format stream-json --verbose < $T/v/$L/prompt-$i.txt > $T/v/$L/stream-$i.jsonl 2> $T/v/$L/stderr-$i.txt) & done; wait
python3 $S/vsumm.py $T $L | cut -c1-430
for i in $(seq 1 $N); do R=$T/rec-$L/$i/record.jsonl; echo "record $i: $(wc -l < $R 2>/dev/null) lines; file names: $(grep -o '[0-9A-Za-z_.]*\.jpg' $R 2>/dev/null | sort -u | wc -l); fake: $(grep -o '[0-9A-Za-z_.]*\.jpg' $R 2>/dev/null | sort -u | while read n; do [ -e $T/n/photos/$n ] || echo -n "$n "; done)"; done
