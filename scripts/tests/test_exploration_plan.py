"""Feedback, hard caps, invalidation and privacy checks for exploration allocation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'exploration_plan.py'
class ExplorationPlanTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'.gitignore').write_text('.local/\nprivate/\n')
        names=[]
        for i in range(14):
            name=f'Example{i:02}.kt';names.append(name)
            (self.root/name).write_text('object Example {\n    val 日本語 = "needle"\n}\n',encoding='utf-8')
        subprocess.run(['git','-C',str(self.root),'add','--',*names],check=True)
        self.state='.local/exploration.json'
    def cli(self,*args):
        return subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),self.state,*args],capture_output=True,text=True)
    def test_feedback_expands_budget_and_stops_at_cap(self):
        for level,args in enumerate([[],['--feedback','insufficient'],['--feedback','insufficient']]):
            result=self.cli('needle',*args)
            self.assertEqual(0,result.returncode,result.stderr);data=json.loads(result.stdout)
            self.assertEqual(level,data['level']);self.assertEqual(3*2**level,data['candidate_budget'])
            self.assertLessEqual(len(result.stdout),data['max_chars'])
            self.assertGreater(data['omitted_candidates'],0)
        result=self.cli('needle','--feedback','insufficient')
        self.assertEqual(1,result.returncode);self.assertEqual('manual_investigation',json.loads(result.stdout)['status'])
    def test_sufficient_feedback_is_explicit_and_changed_input_invalidates_it(self):
        self.assertEqual(0,self.cli('needle').returncode)
        result=self.cli('needle','--feedback','sufficient')
        self.assertEqual('ready_for_edit',json.loads(result.stdout)['status'])
        (self.root/'Example00.kt').write_text('object Changed { val text = "needle" }\n')
        result=self.cli('needle','--feedback','sufficient')
        self.assertEqual(1,result.returncode);self.assertEqual('needs_recheck',json.loads(result.stdout)['status'])
    def test_ranges_and_missing_query(self):
        result=self.cli('needle');data=json.loads(result.stdout)
        self.assertEqual([{'start_line':1,'end_line':3}],data['candidates'][0]['ranges'])
        result=self.cli('absent')
        self.assertEqual(2,result.returncode) # state belongs to another query
        (self.root/self.state).unlink()
        result=self.cli('absent');self.assertEqual(1,result.returncode)
        self.assertEqual('no_matches',json.loads(result.stdout)['status'])
    def test_unstaged_deletion_invalidates_sufficient_assessment(self):
        self.assertEqual(0,self.cli('needle').returncode)
        self.assertEqual(0,self.cli('needle','--feedback','sufficient').returncode)
        (self.root/'Example00.kt').unlink()
        result=self.cli('needle','--feedback','sufficient')
        self.assertEqual(1,result.returncode,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual('needs_recheck',data['status'])
        self.assertEqual(0,data['level'])
        self.assertEqual(13,data['total_candidates'])
        self.assertNotIn('Example00.kt',result.stdout)
    def test_ignored_alias_fails_without_disclosing_content(self):
        private=self.root/'private';private.mkdir();(private/'secret.kt').write_text('PRIVATE_NEEDLE')
        (self.root/'alias.kt').symlink_to(private/'secret.kt')
        subprocess.run(['git','-C',str(self.root),'add','--','alias.kt'],check=True)
        result=self.cli('needle')
        self.assertEqual(2,result.returncode);self.assertEqual('',result.stdout)
        self.assertNotIn('PRIVATE_NEEDLE',result.stderr)
    def test_foreign_state_and_invalid_feedback_do_not_overwrite(self):
        path=self.root/self.state;path.parent.mkdir();path.write_text('{"version":1,"purpose":"another_tool"}')
        before=path.read_bytes();result=self.cli('needle')
        self.assertEqual(2,result.returncode);self.assertEqual(before,path.read_bytes())
        path.unlink();result=self.cli('needle','--feedback','insufficient')
        self.assertEqual(2,result.returncode);self.assertFalse(path.exists())
    def test_untracked_and_private_files_are_outside_search_scope(self):
        (self.root/'new.kt').write_text('needle')
        private=self.root/'private';private.mkdir();(private/'secret.kt').write_text('needle')
        result=self.cli('needle');data=json.loads(result.stdout)
        self.assertEqual(14,data['total_candidates'])
        self.assertNotIn('new.kt',result.stdout);self.assertNotIn('secret.kt',result.stdout)

if __name__=='__main__':unittest.main()
