#!/usr/bin/env python3
"""Validate cloudbuild.yaml and Dockerfile before merge."""
import re, sys, os

errors = []

# 1. Validate cloudbuild.yaml exists and has required sections
try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed")
    sys.exit(1)

with open('cloudbuild.yaml') as f:
    config = yaml.safe_load(f)

if 'steps' not in config:
    errors.append('Missing "steps" section in cloudbuild.yaml')
elif len(config['steps']) < 2:
    errors.append('Need at least build + push steps, found ' + str(len(config['steps'])))

if 'substitutions' not in config:
    errors.append('Missing "substitutions" section in cloudbuild.yaml')

# 2. Check substitution values for nested ${} variables
# Cloud Build does NOT expand substitution references inside other substitution values
content = open('cloudbuild.yaml').read()
subs_section = content.split('substitutions:')[1] if 'substitutions:' in content else ''
nested_vars = re.findall(r':\s*\$\{[^}]+\}', subs_section)
if nested_vars:
    errors.append(
        'Substitution values contain nested variable references: ' + str(nested_vars) +
        '\nThese will NOT be expanded by Cloud Build! Hardcode the values instead.'
    )

# 3. Validate Dockerfile has required commands
dockerfile = 'backend/Dockerfile'
if not os.path.exists(dockerfile):
    errors.append('Dockerfile not found at ' + dockerfile)
else:
    with open(dockerfile) as f:
        df_content = f.read()
    if 'FROM' not in df_content:
        errors.append('Dockerfile missing FROM instruction')
    if 'CMD' not in df_content and 'ENTRYPOINT' not in df_content:
        errors.append('Dockerfile missing CMD or ENTRYPOINT')
    if 'COPY' not in df_content:
        errors.append('Dockerfile missing COPY instruction')

# Report
if errors:
    print('VALIDATION FAILED:')
    for e in errors:
        print('  - ' + e)
    sys.exit(1)

print('cloudbuild.yaml: valid')
print('Dockerfile: valid')
print('No nested substitution variables: OK')
