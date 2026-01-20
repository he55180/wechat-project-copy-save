import markdown
import os
import sys

# This script converts a markdown file to an HTML file.
# It's separated from the YAML to prevent parsing issues.

if not os.path.exists('output/latest_report.md'):
    print("INFO: 'output/latest_report.md' not found. Nothing to convert.", file=sys.stderr)
    sys.exit(0) # Exit successfully, the calling script will handle this case.

try:
    with open('output/latest_report.md', 'r', encoding='utf-8') as f:
        content = f.read()

    html = markdown.markdown(content, extensions=['tables', 'fenced_code'])

    with open('output/report.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("Successfully converted 'output/latest_report.md' to 'output/report.html'.")

except Exception as e:
    print(f"ERROR: An error occurred during conversion: {e}", file=sys.stderr)
    sys.exit(1)
