"""Build the installable Blender extension ZIP using Python's standard library."""
from pathlib import Path
import re
import zipfile

root = Path(__file__).resolve().parent
manifest = (root / 'blender_manifest.toml').read_text(encoding='utf-8')
version = re.search(r'^version\s*=\s*"([^"]+)"', manifest, re.MULTILINE).group(1)
dest = root / 'dist'
dest.mkdir(exist_ok=True)
archive = dest / f'ReSkate-Base-Mask-Packer-{version}.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
    for name in ('__init__.py', 'blender_manifest.toml', 'README.md', 'LICENSE'):
        output.write(root / name, name)
    for asset in sorted((root / 'docs').rglob('*')):
        if asset.is_file():
            output.write(asset, asset.relative_to(root).as_posix())
print(archive)
