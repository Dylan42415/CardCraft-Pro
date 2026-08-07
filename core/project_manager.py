import os
import json
from typing import List, Dict, Optional
from core.models import Project, Layout, PrinterProfile
from core.layout_engine import get_default_layouts

# App configuration directories
USER_DIR = os.path.expanduser("~")
APP_DATA_DIR = os.path.join(USER_DIR, ".gemini", "antigravity", "prepress_app")
LAYOUTS_FILE = os.path.join(APP_DATA_DIR, "custom_layouts.json")
PROFILES_FILE = os.path.join(APP_DATA_DIR, "printer_profiles.json")

def ensure_app_dirs():
    """Ensure that the application data folders exist."""
    os.makedirs(APP_DATA_DIR, exist_ok=True)

def save_project(project: Project, filepath: str) -> None:
    """Saves the project to a JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(project.model_dump_json(indent=4))

def load_project(filepath: str) -> Project:
    """Loads a project from a JSON file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Project file not found: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return Project(**data)

def load_layouts() -> List[Layout]:
    """Loads all layouts, combining defaults and user-defined layouts."""
    ensure_app_dirs()
    layouts = get_default_layouts()
    
    if os.path.exists(LAYOUTS_FILE):
        try:
            with open(LAYOUTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                custom_layouts = [Layout(**item) for item in data]
                
                # Merge custom layouts (override by ID if matched)
                layout_dict = {l.id: l for l in layouts}
                for cl in custom_layouts:
                    layout_dict[cl.id] = cl
                layouts = list(layout_dict.values())
        except Exception as e:
            print(f"Error loading custom layouts: {e}")
            
    return layouts

def save_custom_layouts(custom_layouts: List[Layout]) -> None:
    """Saves the list of user-created layouts to disk."""
    ensure_app_dirs()
    # Filter out defaults so we only save truly custom/modified ones
    default_ids = {l.id for l in get_default_layouts()}
    custom_only = [l for l in custom_layouts if l.id not in default_ids]
    
    with open(LAYOUTS_FILE, 'w', encoding='utf-8') as f:
        json.dump([l.model_dump() for l in custom_only], f, indent=4)

def load_printer_profiles() -> List[PrinterProfile]:
    """Loads all saved printer profiles from user directory."""
    ensure_app_dirs()
    profiles = []
    
    # Add a default profile matching the new PrinterProfile schema
    default_profile = PrinterProfile(
        profile_name="Standard Spot UV Profile",
        layout_id="a4_8_cards_standard",
        print_passes=["Base Artwork", "White Ink", "Gloss", "Emboss"],
        disabled_passes=[],
        mappings={
            "Layer 0 - Red": "Base Artwork",
            "Layer 0 - Green": "Base Artwork",
            "Layer 0 - Blue": "Base Artwork",
            "white ink": "White Ink",
            "1": "White Ink",
            "3": "Emboss"
        },
        disabled_channels=[]
    )
    
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                profiles = [PrinterProfile(**item) for item in data]
        except Exception as e:
            print(f"Error loading printer profiles: {e}")
            
    # Include default profile if not present
    if not any(p.profile_name == default_profile.profile_name for p in profiles):
        profiles.insert(0, default_profile)
        
    return profiles

def save_printer_profiles(profiles: List[PrinterProfile]) -> None:
    """Saves the list of printer profiles to disk."""
    ensure_app_dirs()
    with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump([p.model_dump() for p in profiles], f, indent=4)

def save_printer_profile(profile: PrinterProfile) -> str:
    """Saves a printer profile to both the database and as a standalone JSON file in workspace profiles directory."""
    # 1. Save to database
    profiles = load_printer_profiles()
    updated = False
    for i, p in enumerate(profiles):
        if p.profile_name == profile.profile_name:
            profiles[i] = profile
            updated = True
            break
    if not updated:
        profiles.append(profile)
    save_printer_profiles(profiles)
    
    # 2. Save standalone file in workspace profiles directory
    workspace_profiles_dir = "profiles"
    os.makedirs(workspace_profiles_dir, exist_ok=True)
    filename = "".join(c for c in profile.profile_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
    filepath = os.path.join(workspace_profiles_dir, f"{filename}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(profile.model_dump_json(indent=4))
    return filepath

def load_printer_profile(filepath: str) -> PrinterProfile:
    """Loads a single printer profile from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return PrinterProfile(**data)


class ProjectManager:
    CURRENT_VERSION = 1

    def __init__(self, app_data_dir: str = APP_DATA_DIR):
        self.app_data_dir = app_data_dir
        os.makedirs(self.app_data_dir, exist_ok=True)
        self.recent_file = os.path.join(self.app_data_dir, "recent_projects.json")
        self.autosave_file = os.path.join(self.app_data_dir, "autosave_project.optcgproj")
        self.recent_projects = self.load_recent_projects()

    def load_recent_projects(self) -> List[str]:
        if os.path.exists(self.recent_file):
            try:
                with open(self.recent_file, 'r', encoding='utf-8') as f:
                    projects = json.load(f)
                    # Filter out non-existent files dynamically to keep it clean
                    return [p for p in projects if os.path.exists(p)]
            except Exception as e:
                print(f"Error loading recent projects: {e}")
        return []

    def save_recent_projects(self):
        try:
            with open(self.recent_file, 'w', encoding='utf-8') as f:
                json.dump(self.recent_projects, f, indent=4)
        except Exception as e:
            print(f"Error saving recent projects: {e}")

    def add_recent_project(self, filepath: str):
        filepath = os.path.abspath(filepath)
        if filepath in self.recent_projects:
            self.recent_projects.remove(filepath)
        self.recent_projects.insert(0, filepath)
        self.recent_projects = self.recent_projects[:10]  # Limit to 10
        self.save_recent_projects()

    def clear_recent_projects(self):
        self.recent_projects = []
        self.save_recent_projects()

    def save_project(self, project: Project, filepath: str) -> None:
        project.version = self.CURRENT_VERSION
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(project.model_dump_json(indent=4))
        self.add_recent_project(filepath)

    def load_project(self, filepath: str) -> Project:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Project file not found: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Version check & automatic migration
        version = data.get("version", 0)
        if version < self.CURRENT_VERSION:
            # Future migrations go here (currently v0->v1 matches identical fields)
            data["version"] = self.CURRENT_VERSION
            
        return Project(**data)

    def save_autosave(self, project: Project) -> None:
        try:
            project.version = self.CURRENT_VERSION
            with open(self.autosave_file, 'w', encoding='utf-8') as f:
                f.write(project.model_dump_json(indent=4))
        except Exception as e:
            print(f"Error saving project autosave: {e}")

    def load_autosave(self) -> Optional[Project]:
        if os.path.exists(self.autosave_file):
            try:
                return self.load_project(self.autosave_file)
            except Exception as e:
                print(f"Error loading project autosave: {e}")
        return None

    def clear_autosave(self):
        try:
            if os.path.exists(self.autosave_file):
                os.remove(self.autosave_file)
        except Exception as e:
            print(f"Error clearing project autosave: {e}")
