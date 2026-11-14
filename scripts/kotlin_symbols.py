#!/usr/bin/env python3
"""List Kotlin declarations or read one exact lexical declaration using Tree-sitter."""
import argparse
import ctypes
import subprocess
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from document_tools import Repository, ROOT

KINDS = {'function_declaration', 'class_declaration', 'object_declaration', 'type_alias'}

def declarations(raw, library_path):
    from tree_sitter import Language, Parser
    library = ctypes.CDLL(str(library_path.resolve()))
    library.tree_sitter_kotlin.restype = ctypes.c_void_p
    capsule = ctypes.pythonapi.PyCapsule_New
    capsule.restype = ctypes.py_object
    capsule.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    language = Language(capsule(library.tree_sitter_kotlin(), b'tree_sitter.Language', None))
    tree = Parser(language).parse(raw)
    if tree.root_node.has_error:
        raise ValueError('Kotlin parse contains errors; use original source; no declaration returned')
    result = []
    def visit(node, scope):
        child_scope = scope
        if node.type in KINDS:
            name = node.child_by_field_name('name') or next((child for child in node.named_children if child.type in ['simple_identifier', 'type_identifier']), None)
            if name:
                label = name.text.decode('utf-8').strip('`')
                qualified = '.'.join([*scope, label])
                result.append({'name': label, 'qualified_name': qualified, 'kind': node.type,
                               'start_line': node.start_point.row + 1,
                               'end_line': node.end_point.row + (node.end_point.column > 0),
                               'start_byte': node.start_byte, 'end_byte': node.end_byte})
                child_scope = [*scope, label]
        if node.type == 'object_literal':
            child_scope = [*scope, f'<anonymous@{node.start_point.row + 1}>']
        for child in node.named_children:
            visit(child, child_scope)
    visit(tree.root_node, [])
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('path')
    parser.add_argument('--grammar-library', type=Path, required=True, help='Trusted compiled Kotlin grammar; see tool setup')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--list', action='store_true')
    mode.add_argument('--symbol', help='Exact name or lexical qualified name; ambiguous matches are rejected')
    parser.add_argument('--at-line', type=int, help='Declaration start line to disambiguate overloads')
    parser.add_argument('--max-chars', type=int, default=8000)
    args = parser.parse_args()
    try:
        repository = Repository(args.root)
        git_root = subprocess.run(['git', '-C', str(repository.root), 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True)
        if Path(git_root.stdout.strip()).resolve() != repository.root:
            raise ValueError('root must be the Git repository root')
        path = repository.path(args.path)
        if path.suffix != '.kt':
            raise ValueError('expected a Kotlin .kt source')
        raw = path.read_bytes()
        text = raw.decode('utf-8')
        symbols = declarations(raw, args.grammar_library)
        metadata = {'path': path.relative_to(repository.root).as_posix(),
                    'sha256': hashlib.sha256(raw).hexdigest(),
                    'parser': {'tree-sitter': version('tree-sitter'),
                               'grammar_sha256': hashlib.sha256(args.grammar_library.read_bytes()).hexdigest()}}
        if args.list:
            if args.at_line is not None:
                raise ValueError('--at-line requires --symbol')
            output = json.dumps({**metadata, 'declarations': symbols}, ensure_ascii=False) + '\n'
        else:
            exact = [s for s in symbols if s['qualified_name'] == args.symbol]
            matches = exact or [s for s in symbols if s['name'] == args.symbol]
            if args.at_line is not None:
                matches = [s for s in matches if s['start_line'] == args.at_line]
            if len(matches) != 1:
                raise ValueError('symbol missing or ambiguous; list declarations and qualify the name or line')
            selected = matches[0]
            lines = text.splitlines()
            body = '\n'.join(f'{i + 1}: {lines[i]}' for i in range(selected['start_line'] - 1, selected['end_line']))
            output = json.dumps({**metadata, 'declaration': selected}, ensure_ascii=False) + '\n' + body + '\n'
        if args.max_chars < 1 or len(output) > args.max_chars:
            raise ValueError('result exceeds --max-chars; select one declaration or increase limit; no text returned')
        print(output, end='')
    except ImportError:
        parser.exit(2, 'install optional scripts/requirements-kotlin-tools.txt in an isolated environment\n')
    except (OSError, UnicodeError, AttributeError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{type(error).__name__}: source or trusted grammar unavailable; no text returned\n')
    except ValueError as error:
        parser.exit(1, f'ValueError: {error}\n')

if __name__ == '__main__':
    main()
