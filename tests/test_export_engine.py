import os
import shutil
import tempfile
import pytest
import numpy as np
from PIL import Image
import tifffile

from core.models import Project, Layout, CardSlot, PaperSize, CardSize, MarginSettings, RegistrationSettings, RegistrationPattern
from core import export_engine, project_manager, tiff_parser, layout_engine


@pytest.fixture
def temp_export_dir():
    dirpath = tempfile.mkdtemp(prefix="cardcraft_test_export_")
    yield dirpath
    if os.path.exists(dirpath):
        shutil.rmtree(dirpath)


@pytest.fixture
def mock_card_tiff(temp_export_dir):
    """Creates a sample multi-channel TIFF card file (1488x2079 px, 600 PPI) for testing."""
    w, h = 1488, 2079
    r = np.full((h, w), 200, dtype=np.uint8)
    g = np.full((h, w), 100, dtype=np.uint8)
    b = np.full((h, w), 50, dtype=np.uint8)
    a = np.full((h, w), 255, dtype=np.uint8)
    
    # White Ink spot channel (1)
    w_ink = np.zeros((h, w), dtype=np.uint8)
    w_ink[100:1500, 100:1300] = 255
    
    # Emboss spot channel (3)
    emboss = np.zeros((h, w), dtype=np.uint8)
    emboss[200:1400, 200:1200] = 255
    
    stacked = np.stack([r, g, b, a, w_ink, emboss], axis=-1)
    card_path = os.path.join(temp_export_dir, "test_input_card.tiff")
    
    extra_names = ["Alpha", "1", "3"]
    extra_samples = [2, 0, 0]
    resource_bytes = export_engine.create_photoshop_resource_block(extra_names)
    extratags = [(34377, 1, len(resource_bytes), resource_bytes, True)]
    
    tifffile.imwrite(
        card_path,
        stacked,
        photometric='rgb',
        extrasamples=extra_samples,
        extratags=extratags
    )
    return card_path


@pytest.fixture
def sample_project(mock_card_tiff):
    layouts = project_manager.load_layouts()
    layout = layouts[0] # A4 9 Cards Borderless
    
    slots = []
    for i in range(9):
        slot = CardSlot(
            slot_index=i,
            filepath=mock_card_tiff if i < 3 else None, # Assign to 3 slots
            mappings={"Base Artwork (RGB)": "Base Artwork", "1": "White Ink", "3": "Emboss"} if i < 3 else {}
        )
        slots.append(slot)
        
    project = Project(
        project_name="Test Export Project",
        layout=layout,
        card_slots=slots
    )
    return project


def test_export_layered_tiff(sample_project, temp_export_dir):
    out_path = os.path.join(temp_export_dir, "sheet_layered.tiff")
    res_path, reports = export_engine.export_project(sample_project, out_path, export_type="layered_tiff", ppi=300)
    
    assert os.path.exists(res_path)
    file_size = os.path.getsize(res_path)
    # 300 PPI A4 5-channel sheet must be multi-megabyte (> 1 MB)
    assert file_size > 1_000_000, f"Layered TIFF is suspiciously small: {file_size} bytes"
    
    # Validate TIFF header structure
    with tifffile.TiffFile(res_path) as tf:
        page = tf.pages[0]
        assert page.photometric == tifffile.PHOTOMETRIC.RGB
        # Shape should be (height, width, channels)
        shape = page.shape
        assert len(shape) == 3
        assert shape[2] >= 3 # RGB + extra channels


def test_export_flat_tiff(sample_project, temp_export_dir):
    out_path = os.path.join(temp_export_dir, "sheet_flat.tiff")
    res_path, reports = export_engine.export_project(sample_project, out_path, export_type="flat_tiff", ppi=300)
    
    assert os.path.exists(res_path)
    file_size = os.path.getsize(res_path)
    assert file_size > 500_000, f"Flat TIFF is suspiciously small: {file_size} bytes"
    
    with tifffile.TiffFile(res_path) as tf:
        page = tf.pages[0]
        assert page.shape[2] == 3 # Strict 3-channel RGB


def test_export_png_preview(sample_project, temp_export_dir):
    out_path = os.path.join(temp_export_dir, "sheet_preview.png")
    res_path, reports = export_engine.export_project(sample_project, out_path, export_type="png_preview", ppi=150)
    
    assert os.path.exists(res_path)
    img = Image.open(res_path)
    assert img.mode == "RGBA"


def test_export_pdf_preview(sample_project, temp_export_dir):
    out_path = os.path.join(temp_export_dir, "sheet_preview.pdf")
    res_path, reports = export_engine.export_project(sample_project, out_path, export_type="pdf_preview", ppi=150)
    
    assert os.path.exists(res_path)
    assert os.path.getsize(res_path) > 10000


def test_export_individual_cards(sample_project, temp_export_dir):
    out_dir = os.path.join(temp_export_dir, "individual_cards")
    paths, reports = export_engine.export_individual_cards(sample_project, out_dir, ppi=300)
    
    # 3 active card slots assigned
    assert len(paths) == 3
    for p in paths:
        assert os.path.exists(p)
        assert os.path.getsize(p) > 500_000, f"Individual card TIFF is too small: {os.path.getsize(p)} bytes"


def test_draw_registration_marks(sample_project):
    reg_img = layout_engine.draw_registration_marks(sample_project.layout, ppi=300)
    assert reg_img is not None
    assert reg_img.size[0] > 1000 and reg_img.size[1] > 1000
    assert reg_img.mode == "RGBA"
