#!/usr/bin/env python3
with open(r'D:\Work_project\back_up\Artificial_agent\backend\pipeline\process_gen.py', 'rb') as f:
    data = f.read()

lines = data.split(b'\n')
line139 = lines[138]
print('Line 139 bytes:', [hex(b) for b in line139])

# Check for any unusual characters in line 139
for i, b in enumerate(line139):
    if b > 127 or b < 32:
        print(f'Unusual byte at {i}: {b}')

# Check if there are any escape sequences like \x or \u anywhere in the file around line 139
context = b''.join(lines[135:142])
print('Context around line 139:')
print(repr(context))

# Search for backslash
idx = data.find(b'\\')
while idx != -1 and idx < data.find(b'\n', idx + 100):
    if idx > 0:
        print(f'Backslash at byte {idx}: {data[max(0,idx-10):idx+10]!r}')
    idx = data.find(b'\\', idx + 1)
    if idx > len(data) - 100:
        break