"""Render the real legal HTML documents from the *.example.html templates,
filling in personal data from a .env file.

The templates (legal/privacy.de.example.html, legal/impressum.de.example.html)
are tracked in git and contain [Platzhalter] tokens. The real documents contain
personal data and are gitignored. This script generates them so you don't have
to hand-edit the placeholders each time.

Usage:
    cp legal/.env.example legal/.env      # then fill in legal/.env
    python3 scripts/render_legal.py       # writes legal/privacy.de.html + impressum.de.html
    python3 scripts/render_legal.py --check   # verify only, write nothing

After rendering, upload to S3 (see legal/README.md):
    aws s3 cp legal/privacy.de.html   s3://$BUCKET/legal/... --content-type "text/html; charset=utf-8"
    ...then invalidate CloudFront /legal/*

No third-party dependencies (no python-dotenv needed).
"""

import argparse
import datetime
import html
import os
import sys

LEGAL_DIR = os.path.join(os.path.dirname(__file__), '..', 'legal')


def load_env(path):
    """Minimal .env parser: KEY=VALUE lines, ignores blanks and # comments."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding='utf-8') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            values[key.strip()] = val.strip()
    return values


def build_replacements(env):
    """Map each exact placeholder token (as it appears in the templates) to a
    resolved value. Values are HTML-escaped since they are injected into markup.
    """
    def esc(v):
        return html.escape(v, quote=False)

    name = env.get('LEGAL_NAME', '')
    street = env.get('LEGAL_STREET', '')
    city = env.get('LEGAL_CITY', '')
    country = env.get('LEGAL_COUNTRY', '')
    email = env.get('LEGAL_EMAIL', '')
    representative = env.get('LEGAL_REPRESENTATIVE', '') or name
    phone = env.get('LEGAL_PHONE', '')
    content_resp = env.get('LEGAL_CONTENT_RESPONSIBLE', '') or f'{name}, {street}, {city}'
    dpo = env.get('LEGAL_DPO', '') or 'nicht benannt'
    date = env.get('LEGAL_PRIVACY_DATE', '') or datetime.date.today().strftime('%d.%m.%Y')

    return {
        # shared address block (privacy §1 + impressum)
        '[Name / Einrichtung]': esc(name),
        '[Straße und Hausnummer]': esc(street),
        '[PLZ und Ort]': esc(city),
        '[Land]': esc(country),
        '[kontakt@example.org]': esc(email),
        # impressum specifics
        '[Name der vertretungsberechtigten Person]': esc(representative),
        'Telefon: [optional]': f'Telefon: {esc(phone)}' if phone else '',
        '[Name, Anschrift — falls abweichend]': esc(content_resp),
        # privacy specifics
        '[Name, Kontakt]': esc(dpo),
        '[TT.MM.JJJJ]': esc(date),
    }


def render_file(template_path, out_path, replacements, check_only):
    with open(template_path, encoding='utf-8') as fh:
        content = fh.read()

    # Strip the leading HTML comment block (developer note) from the output.
    if content.lstrip().startswith('<!--'):
        end = content.find('-->')
        if end != -1:
            content = content[end + 3:].lstrip('\n')

    for token, value in replacements.items():
        content = content.replace(token, value)

    # Safety: refuse to publish if any [placeholder] survived.
    import re
    leftover = re.findall(r'\[[^\]]+\]', content)
    # Ignore false positives that are legitimate content (none expected here).
    leftover = [t for t in leftover if t not in ('[]',)]
    if leftover:
        print(f'  ERROR: unresolved placeholders in {os.path.basename(out_path)}: {sorted(set(leftover))}')
        return False

    if check_only:
        print(f'  OK (check): {os.path.basename(out_path)} would render cleanly')
        return True

    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(content)
    print(f'  wrote {out_path}')
    return True


def main():
    parser = argparse.ArgumentParser(description='Render legal HTML from templates + .env')
    parser.add_argument('--check', action='store_true',
                        help='Verify placeholders resolve; do not write files')
    parser.add_argument('--env', default=os.path.join(LEGAL_DIR, '.env'),
                        help='Path to the .env file (default: legal/.env)')
    args = parser.parse_args()

    env = load_env(args.env)
    if not env:
        print(f'No values loaded from {args.env}.')
        print('Copy legal/.env.example to legal/.env and fill it in first.')
        sys.exit(1)

    replacements = build_replacements(env)

    docs = [
        ('privacy.de.example.html', 'privacy.de.html'),
        ('impressum.de.example.html', 'impressum.de.html'),
    ]

    print('=== Rendering legal documents ===')
    print(f'Env file : {args.env}')
    print(f'Mode     : {"check" if args.check else "write"}')
    print()

    ok = True
    for template_name, out_name in docs:
        template_path = os.path.join(LEGAL_DIR, template_name)
        out_path = os.path.join(LEGAL_DIR, out_name)
        if not os.path.exists(template_path):
            print(f'  ERROR: template not found: {template_path}')
            ok = False
            continue
        ok = render_file(template_path, out_path, replacements, args.check) and ok

    print()
    if not ok:
        print('Failed — see errors above.')
        sys.exit(1)
    print('Done.' if not args.check else 'Check passed.')
    if not args.check:
        print('Next: upload to S3 and invalidate CloudFront (see legal/README.md).')


if __name__ == '__main__':
    main()
