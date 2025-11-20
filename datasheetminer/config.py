import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Dict, Type


from datasheetminer.models.product import ProductBase


REGION: str = "us-east-1"

GUARDRAILS: str = """
"""

MODEL: str = "gemini-2.5-flash"  # Explicitly define model for clarity


def _discover_schema_models() -> Dict[str, Type[ProductBase]]:
    """
    Automatically discover all Pydantic model schemas in the models directory.

    This function scans datasheetminer/models/ for Python modules and imports
    any classes that inherit from BaseModel, using the module name as the key.

    Excludes base classes and utility modules (common, product).

    For example:
    - datasheetminer/models/motor.py -> Motor class -> "motor": Motor
    - datasheetminer/models/robot_arm.py -> RobotArm class -> "robot_arm": RobotArm

    Returns:
        Dict mapping model name (lowercase, underscored) to Pydantic model class

    Note: This eliminates the need to manually update SCHEMA_CHOICES when
          adding new product types. Just create a new model file and it will
          automatically be discovered.
    """
    schema_choices: Dict[str, Type[ProductBase]] = {}

    # Modules to skip (base classes, utilities)
    EXCLUDED_MODULES = {"common", "product", "__init__"}

    # Get the models directory path
    models_dir = Path(__file__).parent / "models"

    if not models_dir.exists():
        return schema_choices

    # Iterate through all Python modules in the models directory
    for module_info in pkgutil.iter_modules([str(models_dir)]):
        module_name = module_info.name

        # Skip __init__, private modules, and excluded base classes
        if module_name.startswith("_") or module_name in EXCLUDED_MODULES:
            continue

        try:
            # Import the module
            module = importlib.import_module(f"datasheetminer.models.{module_name}")

            # Find all classes in the module that inherit from BaseModel
            for _, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a Pydantic model (inherits from ProductBase)
                # and is defined in this module (not imported)
                if (
                    issubclass(obj, ProductBase)
                    and obj is not ProductBase
                    and obj.__module__ == module.__name__
                ):
                    # Use the module name as the key (e.g., "motor", "robot_arm")
                    schema_choices[module_name] = obj
                    print(f"Discovered schema: {module_name} -> {obj.__name__}")
                    break  # Only take the first/main model from each module

        except (ImportError, AttributeError) as e:
            # Log but don't fail - some modules might not be valid
            print(f"Warning: Could not import model from {module_name}: {e}")
            continue

    return schema_choices


# Auto-discover all schema models from the models directory
# This replaces the manual dictionary definition
SCHEMA_CHOICES: Dict[str, Type[ProductBase]] = _discover_schema_models()
