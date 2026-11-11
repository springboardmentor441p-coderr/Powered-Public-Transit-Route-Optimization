"""Issue-time supply feature checks and paired experiment reconciliation."""
import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from service_feature_experiment import schedule_gate
class ServiceFeatureTests(unittest.TestCase):
 def test_capture_boundary_quality_and_nonpositive_service(self):
  base={'payment_date':'2026-06-01','source_snapshot':'manhattan_20260531','prior_source_snapshot':'manhattan_20260530','schedule_comparison_eligible':True,'scheduled_departures':12,'scheduled_service_hours':8}
  rows=[base,{**base,'source_snapshot':'manhattan_20260601'},{**base,'prior_source_snapshot':None},{**base,'schedule_comparison_eligible':False},{**base,'scheduled_departures':0}]
  self.assertEqual(schedule_gate(pd.DataFrame(rows)).tolist(),[True,False,False,False,False])
 def test_common_scoring_population(self):
  p=Path(__file__).resolve().parents[1]/'data/processed/new_york/service_feature_experiment/predictions.csv'
  if not p.exists():self.skipTest('Experiment products not installed')
  x=pd.read_csv(p);self.assertFalse(x.duplicated(['split','model','bus_route','payment_date']).any());self.assertTrue(x.groupby(['split','bus_route','payment_date']).model.nunique().eq(5).all());self.assertTrue(x.prediction.ge(0).all())
