"""Optional Kotlin AST integration checks; run in the documented tool environment."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'kotlin_symbols.py'
LIBRARY = os.environ.get('KOTLIN_GRAMMAR_LIBRARY')
AVAILABLE = importlib.util.find_spec('tree_sitter') is not None and LIBRARY is not None

@unittest.skipUnless(AVAILABLE, 'optional Kotlin tools are not installed')
class KotlinSymbolsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'.gitignore').write_text('.local/\nprivate/\n')
        self.source = self.root/'example.kt'
        self.source.write_text('class 日本語 {\n    fun parse(text: String): String {\n        val marker = "} fun fake() {"\n        // } fun hidden() {}\n        return text + marker\n    }\n    class Nested {\n        fun parse(): String = "終端"\n    }\n    fun read(x: Int) = x\n    fun read(x: String) = x\n}\n',encoding='utf-8')
    def cli(self,*args):
        return subprocess.run([sys.executable,str(SCRIPT),'--root',str(self.root),'--grammar-library',LIBRARY,*args],capture_output=True,text=True)
    def test_exact_lexical_declaration_ignores_comments_and_string_braces(self):
        result=self.cli('example.kt','--symbol','日本語.parse')
        self.assertEqual(0,result.returncode,result.stderr)
        header,body=result.stdout.split('\n',1);data=json.loads(header)
        self.assertEqual((2,6),(data['declaration']['start_line'],data['declaration']['end_line']))
        expected='\n'.join(f'{i}: {line}' for i,line in enumerate(self.source.read_text().splitlines(),1) if 2<=i<=6)+'\n'
        self.assertEqual(expected,body)
        raw=self.source.read_bytes();node=data['declaration']
        self.assertTrue(raw[node['start_byte']:node['end_byte']].startswith(b'fun parse'))
    def test_ambiguous_names_and_overloads_require_qualification_or_line(self):
        for name in ['parse','日本語.read']:
            result=self.cli('example.kt','--symbol',name)
            self.assertNotEqual(0,result.returncode);self.assertEqual('',result.stdout)
        result=self.cli('example.kt','--symbol','日本語.read','--at-line','11')
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertIn('fun read(x: String)',result.stdout)
        self.assertNotIn('fun read(x: Int)',result.stdout)
    def test_listing_returns_real_declarations_only(self):
        result=self.cli('example.kt','--list')
        self.assertEqual(0,result.returncode,result.stderr)
        names=[item['qualified_name'] for item in json.loads(result.stdout)['declarations']]
        self.assertIn('日本語.Nested.parse',names)
        self.assertEqual(6,len(names))
        self.assertFalse(any('fake' in name or 'hidden' in name for name in names))
    def test_parse_error_and_budget_never_return_partial_source(self):
        result=self.cli('example.kt','--symbol','日本語.parse','--max-chars','10')
        self.assertNotEqual(0,result.returncode);self.assertEqual('',result.stdout)
        self.source.write_text('class Broken { fun parse(\n')
        result=self.cli('example.kt','--list')
        self.assertNotEqual(0,result.returncode);self.assertEqual('',result.stdout)
    def test_private_external_and_git_paths_are_rejected(self):
        private=self.root/'private';private.mkdir();(private/'secret.kt').write_text('object Secret {}')
        (self.root/'alias.kt').symlink_to(private/'secret.kt')
        for name in ['private/secret.kt','alias.kt','../outside.kt','.git/config']:
            result=self.cli(name,'--list')
            self.assertNotEqual(0,result.returncode);self.assertEqual('',result.stdout)
    def test_utf8_error_is_atomic(self):
        self.source.write_bytes(b'\xff')
        result=self.cli('example.kt','--list')
        self.assertNotEqual(0,result.returncode);self.assertEqual('',result.stdout)

if __name__=='__main__':unittest.main()
