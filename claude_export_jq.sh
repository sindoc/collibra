#!/usr/bin/env bash
# claude_export_jq.sh — jq-based Claude export → markdown
# Completes the pattern from the example in the conversation.
# For the full s.* function version, see: claude_export_processor.sh
#
# Usage: ./claude_export_jq.sh /path/to/extracted_export_folder [--logseq]

set -euo pipefail

EXPORT_DIR="${1:-./claude_export}"
OUTPUT_DIR="./claude_conversations_md"
LOGSEQ="${2:-}"
mkdir -p "$OUTPUT_DIR"

# ── find export JSON ──────────────────────────────────────────────────────────
MAIN_JSON=$(find "$EXPORT_DIR" -maxdepth 3 -name "*.json" -not -name ".*" \
            2>/dev/null | head -1 || true)

if [[ -z "$MAIN_JSON" ]]; then
  echo "No JSON file found in $EXPORT_DIR" >&2
  exit 1
fi

echo "Processing $MAIN_JSON ..." >&2

# ── detect if jq is available; fall back to python3 ──────────────────────────
if command -v jq &>/dev/null; then
  _BACKEND=jq
else
  _BACKEND=python3
  echo "(jq not found — using python3 backend)" >&2
fi

# ── extract conversations ─────────────────────────────────────────────────────
_conv_count=0

if [[ "$_BACKEND" == "jq" ]]; then
  # jq path — handles root array, {conversations:[...]}, or single object
  jq -c '
    if type == "array" then .[]
    elif has("conversations") then .conversations[]
    else .
    end
  ' "$MAIN_JSON" | while IFS= read -r conv; do

    title=$(echo "$conv" | jq -r '.title // .name // "untitled"')
    cid=$(echo "$conv"   | jq -r '.uuid  // .id   // ""')
    created=$(echo "$conv" | jq -r '.created_at // .created // ""')

    safe_title=$(echo "$title" | tr -s ' ' '_' | tr -cd '[:alnum:]_\-' | head -c 80)
    out_file="${OUTPUT_DIR}/${safe_title}.md"

    {
      # Front matter
      if [[ "$LOGSEQ" == "--logseq" ]]; then
        echo "title:: ${title}"
        echo "claude-conversation-id:: ${cid}"
        echo "created:: ${created}"
        echo "tags:: claude-export, conversation"
        echo ""
      else
        echo "---"
        echo "title: \"${title}\""
        echo "claude_id: ${cid}"
        echo "created: ${created}"
        echo "tags: [claude-export, conversation]"
        echo "---"
        echo ""
      fi

      echo "# ${title}"
      echo ""

      # Messages — handles both .messages[] and .chat_messages[]
      echo "$conv" | jq -r '
        (.chat_messages // .messages // [])[] |
        (
          .content as $c |
          ($c | if type == "array" then map(.text // .content // "") | join("\n")
                else tostring end) as $text |
          if   (.role // .sender) == "user"      then "**Human:** \($text)\n"
          elif (.role // .sender) == "human"     then "**Human:** \($text)\n"
          elif (.role // .sender) == "assistant" then "\n**Assistant:** \($text)\n"
          elif (.role // .sender) == "claude"    then "\n**Assistant:** \($text)\n"
          else "\n**[" + (.role // .sender // "?") + "]:** \($text)\n"
          end
        )
      '

      # s.* annotations footer
      echo ""
      echo "---"
      echo "## s.* Annotations"
      echo ""
      echo "| Key | Value |"
      echo "|-----|-------|"
      echo "| \`s.ref\` | \`c.conv.${cid}\` |"
      echo "| \`s.validate\` | See [[SBVR Rules]] |"
      echo "| \`s.log level\` | INFO |"

    } > "$out_file"

    echo "  EXPORTED: $out_file" >&2
    _conv_count=$(( _conv_count + 1 ))
  done

else
  # python3 fallback (no jq required)
  python3 - "$MAIN_JSON" "$OUTPUT_DIR" "$LOGSEQ" <<'PYEOF'
import json, sys, re, os

main_json, outdir, logseq_flag = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ''
logseq = logseq_flag == '--logseq'

with open(main_json) as f:
    raw = json.load(f)

if isinstance(raw, list):
    convs = raw
elif isinstance(raw, dict) and 'conversations' in raw:
    convs = raw['conversations']
elif isinstance(raw, dict):
    convs = [raw]
else:
    convs = []

exported = 0
for conv in convs:
    if not isinstance(conv, dict): continue
    title   = conv.get('title', conv.get('name', 'untitled'))
    cid     = conv.get('uuid',  conv.get('id',   ''))
    created = conv.get('created_at', conv.get('created', ''))
    msgs    = conv.get('chat_messages', conv.get('messages', []))

    safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:80]
    out_path = os.path.join(outdir, f'{safe}.md')
    lines = []

    if logseq:
        lines += [f'title:: {title}', f'claude-conversation-id:: {cid}',
                  f'created:: {created}', 'tags:: claude-export, conversation', '']
    else:
        lines += ['---', f'title: "{title}"', f'claude_id: {cid}',
                  f'created: {created}', 'tags: [claude-export, conversation]', '---', '']

    lines += [f'# {title}', '']

    for m in msgs:
        role    = m.get('role', m.get('sender', '?'))
        content = m.get('content', m.get('text', ''))
        if isinstance(content, list):
            content = '\n'.join(
                p.get('text', p.get('content', '')) if isinstance(p, dict) else str(p)
                for p in content)
        content = str(content).strip()

        if role in ('user', 'human'):
            lines += [f'**Human:** {content}', '']
        elif role in ('assistant', 'claude'):
            lines += ['', f'**Assistant:** {content}', '']
        else:
            lines += [f'**[{role}]:** {content}', '']

    lines += ['', '---', '## s.* Annotations', '',
              '| Key | Value |', '|-----|-------|',
              f'| `s.ref` | `c.conv.{cid}` |',
              '| `s.validate` | See [[SBVR Rules]] |',
              '| `s.log level` | INFO |']

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f'  EXPORTED: {out_path} ({len(msgs)} messages)', file=sys.stderr)
    exported += 1

print(f'Done: {exported}/{len(convs)} conversations', file=sys.stderr)
PYEOF
fi

echo "Done → $OUTPUT_DIR" >&2
