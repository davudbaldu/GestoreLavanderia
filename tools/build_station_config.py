"""Copy only the public frontend connection config into the executable bundle."""
import argparse
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--output', required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
text=(root/'docs'/'backend-config.js').read_text(encoding='utf-8')
config=json.loads(text[text.index('{'):text.rindex('}')+1])
if not config['publishableKey'].startswith('sb_publishable_'):
    raise SystemExit('Refusing to bundle a non-publishable key')
output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(config),encoding='utf-8')
