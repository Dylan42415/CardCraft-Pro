from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum

class RegistrationPattern(str, Enum):
    THREE = "THREE"
    FOUR = "FOUR"

class PaperSize(BaseModel):
    width_mm: float
    height_mm: float

class CardSize(BaseModel):
    width_mm: float
    height_mm: float
    radius_mm: float = 3.0

class MarginSettings(BaseModel):
    top_mm: float
    bottom_mm: float
    left_mm: float
    right_mm: float

class RegistrationSettings(BaseModel):
    pattern: RegistrationPattern = RegistrationPattern.THREE
    inset_mm: float = 10.0
    length_mm: float = 5.0
    thickness_mm: float = 1.0

class Layout(BaseModel):
    id: str
    name: str
    paper_size: PaperSize
    card_size: CardSize
    rows: int
    columns: int
    card_spacing_mm: float = 1.25
    bleed_mm: float = 1.5
    margins: MarginSettings
    registration: RegistrationSettings

class MappingEntry(BaseModel):
    source_pattern: str  # Regular expression or exact match for imported TIFF channel name
    target_layer: str    # e.g., "Base Artwork", "White Ink", "Emboss", "Gloss"

class PrinterProfile(BaseModel):
    profile_name: str
    layout_id: str = "a4_8_cards_standard"
    print_passes: List[str] = Field(default_factory=list)
    disabled_passes: List[str] = Field(default_factory=list)
    mappings: Union[Dict[str, str], List[MappingEntry], List[dict]] = Field(default_factory=dict)
    disabled_channels: List[str] = Field(default_factory=list)

class CardSlot(BaseModel):
    slot_index: int
    filepath: Optional[str] = None  # Absolute path to TIFF file
    rotation: int = 0               # 0, 90, 180, 270 degrees
    # Maps detected channel name from the TIFF to the target print pass (e.g. "Spot 1" -> "White Ink")
    mappings: Dict[str, str] = Field(default_factory=dict)
    # List of channel names that have been manually unchecked/disabled by the user
    disabled_channels: List[str] = Field(default_factory=list)
    # Slot-specific dithering settings (e.g. enabled, algo, strength, preserve_opaque)
    dither_settings: Dict[str, str] = Field(default_factory=dict)

class Project(BaseModel):
    version: int = 1
    project_name: str
    layout: Layout
    printer_profile: Optional[PrinterProfile] = None
    # Ordered list of print passes/channels, representing the print sequence
    print_passes: List[str] = Field(default_factory=lambda: ["Base Artwork", "White Ink", "Emboss", "Gloss"])
    # List of print pass names that are currently disabled/checked off by the user
    disabled_passes: List[str] = Field(default_factory=lambda: ["Gloss"])
    # All slots in the layout grid
    card_slots: List[CardSlot] = Field(default_factory=list)
    export_settings: Dict[str, str] = Field(default_factory=dict)
