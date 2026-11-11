"""Score an immutable registered forecast when later mature observations are available."""
import argparse
import json
from pathlib import Path
from forecast_intervals import evaluate_registration

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration',required=True,help='Registry folder relative to repository root')
    parser.add_argument('--snapshot',required=True,help='Validated monitoring snapshot relative to repository root')
    args=parser.parse_args()
    print(json.dumps(evaluate_registration(Path(__file__).resolve().parents[1],args.registration,args.snapshot),indent=2))
