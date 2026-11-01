import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image, ImageChops, ImageDraw

import recreation_tools as tool


@pytest.fixture
def task(tmp_path):
    source = Image.new('RGB', (240, 160), 'white')
    draw = ImageDraw.Draw(source)
    draw.rectangle((25, 25, 70, 90), fill='blue')
    draw.line((50, 120, 150, 120), fill='red', width=3)
    source.save(tmp_path / 'source.png')
    (tmp_path / 'regions.json').write_text(json.dumps({'regions': [
        {'id': 'page', 'box': [20, 20, 80, 100]}, {'id': 'arrow', 'box': [40, 110, 160, 130]}]}))
    return tmp_path, source


def test_batch_crops_and_same_scale_comparison_reuse_exact_source_regions(task):
    root, source = task
    before = (root / 'source.png').read_bytes()
    first = tool.run(root, 'source.png', 'inspect', region_file='regions.json', grid=50)
    assert first['source']['sha256'] == hashlib.sha256(before).hexdigest()
    assert Image.open(first['regions'][0]['source_crop']).size == (60, 80)
    source.save(root / 'render.png')
    result = tool.run(root, 'source.png', 'comparison', region_file='inspect/receipt.json', render_path='render.png')
    assert not Image.open(result['outputs']['difference']).getbbox()
    pair = Image.open(result['outputs']['source_left_render_right'])
    assert pair.size == (480, 160)  # region named page must not overwrite full-page diagnostics
    assert not ImageChops.difference(pair.crop((0, 0, 240, 160)), source).getbbox()
    assert not ImageChops.difference(pair.crop((240, 0, 480, 160)), source).getbbox()
    assert not result['inspection_claimed'] and not result['quality_assessed']
    assert before == (root / 'source.png').read_bytes()


def test_render_change_visible_at_exact_source_region(task):
    root, source = task
    render = source.copy(); ImageDraw.Draw(render).rectangle((25, 25, 70, 90), fill='green')
    render.save(root / 'render.png')
    result = tool.run(root, 'source.png', 'compare', region_file='regions.json', render_path='render.png')
    pair = Image.open(result['regions'][0]['source_left_render_right'])
    assert pair.getpixel((20, 20)) == (0, 0, 255)
    assert pair.getpixel((80, 20)) == (0, 128, 0)


def test_source_identity_mismatch_is_not_silently_reused(task):
    root, source = task
    tool.run(root, 'source.png', 'inspect', region_file='regions.json')
    source.putpixel((0, 0), (255, 0, 0)); source.save(root / 'source.png')
    with pytest.raises(ValueError, match='different source'):
        tool.run(root, 'source.png', 'bad', region_file='inspect/receipt.json')
    assert not (root / 'bad').exists()


def test_letterbox_requires_explicit_content_region(task):
    root, source = task
    wide = Image.new('RGB', (320, 160), 'white'); wide.paste(source, (40, 0)); wide.save(root / 'render.png')
    with pytest.raises(ValueError, match='Aspect ratios differ'):
        tool.run(root, 'source.png', 'bad', render_path='render.png')
    result = tool.run(root, 'source.png', 'good', render_path='render.png', render_box=[40, 0, 280, 160])
    assert not Image.open(result['outputs']['difference']).getbbox()
    assert result['render']['content_box'] == [40, 0, 280, 160]


@pytest.mark.parametrize('region', [
    {'id': '../escape', 'box': [0, 0, 10, 10]}, {'id': 'outside', 'box': [-1, 0, 10, 10]},
    {'id': 'fraction', 'box': [0, 0, 10.5, 10]}, {'id': 'empty', 'box': [0, 0, 0, 10]},
])
def test_invalid_regions_write_nothing(task, region):
    root, _ = task
    (root / 'bad.json').write_text(json.dumps({'regions': [region]}))
    with pytest.raises(ValueError):
        tool.run(root, 'source.png', 'bad', region_file='bad.json')
    assert not (root / 'bad').exists()


def test_scopes_symlinks_and_output_overwrite_are_rejected(task):
    root, _ = task
    (root / 'linked.png').symlink_to(root / 'source.png')
    with pytest.raises(ValueError, match='symlink'):
        tool.run(root, 'linked.png', 'bad')
    with pytest.raises(ValueError, match='task root'):
        tool.run(root, '../source.png', 'bad')
    tool.run(root, 'source.png', 'good')
    old = (root / 'good/receipt.json').read_bytes()
    with pytest.raises(ValueError, match='fresh output'):
        tool.run(root, 'source.png', 'good')
    assert old == (root / 'good/receipt.json').read_bytes()


def test_exif_orientation_and_transparency_are_explicit(tmp_path):
    image = Image.new('RGB', (80, 40), 'blue')
    exif = image.getexif(); exif[274] = 6
    image.save(tmp_path / 'rotated.jpg', exif=exif)
    result = tool.run(tmp_path, 'rotated.jpg', 'oriented')
    assert result['source']['oriented_pixels'] == [40, 80]
    Image.new('RGBA', (80, 40), (0, 0, 0, 0)).save(tmp_path / 'transparent.png')
    loaded, _ = tool.load_image(tmp_path, 'transparent.png')
    assert loaded.getpixel((0, 0)) == (255, 255, 255)


def test_cli_works_from_unrelated_working_directory(task, tmp_path):
    root, _ = task
    cmd = [sys.executable, str(Path(tool.__file__).resolve()), 'inspect', '--task-root', str(root),
           '--source', 'source.png', '--regions', 'regions.json', '--out', 'cli']
    process = subprocess.run(cmd, cwd='/tmp', capture_output=True, text=True)
    assert process.returncode == 0, process.stdout + process.stderr
    assert Path(json.loads(process.stdout)['receipt']).is_file()
