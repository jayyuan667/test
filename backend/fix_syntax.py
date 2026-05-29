#!/usr/bin/env python3
import ast

with open(r'D:\Work_project\back_up\Artificial_agent\backend\pipeline\process_gen_BACKUP.py', 'rb') as f:
    content = f.read()

lines = content.split(b'\n')
print(f"Line 139: {lines[138]!r}")
print(f"Line 140: {lines[139]!r}")
print(f"Line 141: {lines[140]!r}")

# Replace line 139 with simpler type annotation and remove line 140's docstring start
# The issue is that line 139 ends with `Optional[Dict[str, Any]]:` and line 140 starts `"""Generate`
# Replace line 139 with the simple types (not using typing.List/Dict)
new_line139 = b'    ) -> Tuple[str, list, Optional[dict]]:'
new_line140 = b'        """Generate process specifications.'

new_lines = lines[:138] + [new_line139, new_line140] + lines[141:]

new_content = b'\n'.join(new_lines)
print(f"New content lines: {new_content.count(b'\\n')}")
print(f"New line 139: {new_lines[138]!r}")
print(f"New line 140: {new_lines[139]!r}")

try:
    ast.parse(new_content.decode('utf-8'))
    print("New content parses OK!")
except SyntaxError as e:
    print(f"Still fails: {e}")
    # Find the actual problem
    for i, line in enumerate(new_lines[:145], 1):
        print(f"{i}: {line!r}")
    exit(1)

with open(r'D:\Work_project\back_up\Artificial_agent\backend\pipeline\process_gen.py', 'wb') as f:
    f.write(new_content)
print("Written to process_gen.py")